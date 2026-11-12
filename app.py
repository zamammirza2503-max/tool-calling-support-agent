import json

import streamlit as st

import database as db
from agent import ProjectAgent
from llm import friendly_error

st.set_page_config(page_title="Electrical Project Assistant", page_icon="🔌", layout="wide")
db.init_db()

st.title("🔌 Electrical Project Assistant")
st.caption(
    f"Tool-calling agent demo for the fictional project **{db.PROJECT}**. The AI cannot see the "
    "database — it asks to call Python functions (part search, device lookup, cable checks, BOM...), "
    "and the app runs them and returns the results."
)

EXAMPLES = [
    "Check all cables for protection problems.",
    "What is -F14 and what is connected to it?",
    "Is the voltage drop on -W13 OK?",
    "Which devices are in cabinet 2?",
    "I need an inverter for at least 5 A. What do we have in stock?",
    "Create the bill of materials for CAB1.",
    "Create a change request to fix the problem on -W14.",
]

with st.sidebar:
    st.header("Demo project")
    st.write(f"**{db.PROJECT}**")
    st.write("Cabinets **CAB1**, **CAB2** · field devices **FIELD**")
    st.divider()
    st.subheader("Try asking")
    for q in EXAMPLES:
        if st.button(q, use_container_width=True):
            st.session_state.pending = q
    st.divider()
    crs = db.list_change_requests()
    st.subheader(f"Change requests ({len(crs)})")
    for cr in crs:
        st.caption(f"**CR-{cr['id']:03d}** {cr['title']} — {cr['affected_tags']} · {cr['status']}")
    if st.button("🔄 Reset chat and demo data", use_container_width=True):
        db.init_db(reset=True)
        st.session_state.clear()
        st.rerun()

st.session_state.setdefault("model_history", [])  # what the LLM sees
st.session_state.setdefault("chat", [])           # what the UI shows


def show_steps(steps):
    if not steps:
        return
    with st.expander(f"🔧 Agent steps: {len(steps)} tool call(s) — " + ", ".join(s["tool"] for s in steps)):
        for n, s in enumerate(steps, start=1):
            st.markdown(f"**{n}. `{s['tool']}`** with arguments `{s['arguments'] or '{}'}`")
            st.code(json.dumps(s["result"], indent=2, ensure_ascii=False)[:3000], language="json")


for turn in st.session_state.chat:
    with st.chat_message(turn["role"]):
        st.markdown(turn["content"])
        show_steps(turn.get("steps"))

prompt = st.chat_input("Ask about devices, parts, cables, checks, BOM...")
prompt = prompt or st.session_state.pop("pending", None)

if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        try:
            with st.spinner("The agent is working with the project tools..."):
                answer, steps, history = ProjectAgent().run(st.session_state.model_history, prompt)
        except Exception as e:
            st.error(friendly_error(e))
            st.stop()
        st.markdown(answer)
        show_steps(steps)
    # keep the context small, but always cut at the start of a user turn
    recent = history[-30:]
    while recent and recent[0].get("role") != "user":
        recent = recent[1:]
    st.session_state.model_history = recent
    st.session_state.chat += [{"role": "user", "content": prompt},
                              {"role": "assistant", "content": answer, "steps": steps}]
    if any(s["tool"] == "create_change_request" for s in steps):
        st.rerun()  # refresh the change request list in the sidebar
