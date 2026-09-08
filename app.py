import os

import streamlit as st
from dotenv import load_dotenv

from agent import SupportAgent
from database import init_db

load_dotenv()
init_db()

st.set_page_config(page_title="Tool-Calling Support Agent")
st.title("Tool-Calling Support Agent")
st.caption("LLM + function calling + SQLite business tools.")

customer_id = st.sidebar.selectbox("Customer", ["C001", "C002"])

if not os.getenv("OPENAI_API_KEY"):
    st.warning("Set OPENAI_API_KEY in .env before using the agent.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

user_message = st.chat_input("Ask about an order or request support")

if user_message:
    st.session_state.messages.append({"role": "user", "content": user_message})
    with st.chat_message("user"):
        st.write(user_message)

    agent = SupportAgent(
        customer_id=customer_id,
        model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
    )

    with st.chat_message("assistant"):
        with st.spinner("The agent is checking its tools..."):
            answer, tools_used = agent.run(user_message)
        st.write(answer)
        if tools_used:
            st.caption("Tools used: " + ", ".join(tools_used))

    st.session_state.messages.append({"role": "assistant", "content": answer})
