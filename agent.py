"""Tool-calling agent.

The LLM never touches the database directly. It can only *ask* to call one of
the Python functions described in TOOLS. Our code checks the request, runs the
function and sends the result back. The loop repeats until the model answers
in plain text (or a step limit is reached).
"""
import json

import database as db
from llm import chat, make_client


def tool(name, description, properties=None, required=None):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties or {}, "required": required or []},
        },
    }


TOOLS = [
    tool("search_parts", "Search the company part master data (circuit breakers, inverters, motors, relays...).",
         {"query": {"type": "string", "description": "Free text, e.g. 'inverter' or 'C20'"},
          "category": {"type": "string", "description": "Optional category, e.g. 'circuit breaker'"},
          "min_rated_current_a": {"type": "number", "description": "Optional minimum rated current in A"}}),
    tool("get_device", "Get one device of the project by its tag (e.g. -F14), with part data and connected cables.",
         {"tag": {"type": "string"}}, ["tag"]),
    tool("list_cabinet_devices", "List all devices installed in a location: CAB1, CAB2 or FIELD.",
         {"cabinet": {"type": "string"}}, ["cabinet"]),
    tool("check_cable_protection",
         "Check whether cables are protected correctly (protective device rating vs. cable cross-section). "
         "Leave cable_tag empty to check all cables of the project.",
         {"cable_tag": {"type": "string", "description": "e.g. -W14; omit to check all cables"}}),
    tool("calculate_voltage_drop", "Calculate the voltage drop of a 400 V three-phase cable and compare it with the 3 % limit.",
         {"cable_tag": {"type": "string"},
          "current_a": {"type": "number", "description": "Optional load current; default is the protective device rating"}},
         ["cable_tag"]),
    tool("generate_bom", "Generate the bill of materials (quantities and prices) for one cabinet or the whole project.",
         {"cabinet": {"type": "string", "description": "CAB1, CAB2 or FIELD; omit for the whole project"}}),
    tool("create_change_request",
         "Create a DRAFT change request. Only use this when the user explicitly asks to create one.",
         {"title": {"type": "string"}, "description": {"type": "string"},
          "affected_tags": {"type": "array", "items": {"type": "string"}}},
         ["title", "description", "affected_tags"]),
]

FUNCTIONS = {
    "search_parts": db.search_parts,
    "get_device": db.get_device,
    "list_cabinet_devices": db.list_cabinet_devices,
    "check_cable_protection": db.check_cable_protection,
    "calculate_voltage_drop": db.calculate_voltage_drop,
    "generate_bom": db.generate_bom,
    "create_change_request": db.create_change_request,
}

SYSTEM_PROMPT = f"""You are a project assistant for electrical design engineers working on the project
"{db.PROJECT}" (function aspect {db.FUNCTION}, cabinets CAB1 and CAB2, field devices in FIELD).

Rules:
- Get every project fact (devices, parts, cables, prices, check results) from the tools. Never invent tags,
  part numbers, ratings or prices.
- When a check finds a problem, explain it in plain words and give the suggested fix.
- Only create a change request when the user explicitly asks for it. Always say it is a draft that an
  engineer must approve.
- The data and the rule values are demo values, not a substitute for a real engineering check.
- Answer concisely. Use short tables or lists for several items. Mention the device tags you talk about.
"""

MAX_STEPS = 6


class ProjectAgent:
    def __init__(self):
        self.client = make_client()

    def _execute(self, name, raw_args):
        if name not in FUNCTIONS:
            return {"error": f"Unknown tool {name}"}
        try:
            args = json.loads(raw_args or "{}")
            args = {k: v for k, v in args.items() if v not in (None, "")}
            return FUNCTIONS[name](**args)
        except Exception as e:  # wrong arguments etc. -> tell the model, don't crash
            return {"error": f"{type(e).__name__}: {e}"}

    def run(self, history, user_message):
        """history: earlier messages (list of dicts). Returns (answer, steps, new_history)."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
        messages.append({"role": "user", "content": user_message})
        steps = []

        for _ in range(MAX_STEPS):
            response = chat(self.client, messages=messages, tools=TOOLS)
            msg = response.choices[0].message
            # Keep the assistant message exactly as returned (Gemini adds thought signatures
            # to tool calls that must be sent back unchanged).
            messages.append(msg.model_dump(exclude_none=True))

            if not msg.tool_calls:
                return msg.content or "", steps, messages[1:]

            for call in msg.tool_calls:
                result = self._execute(call.function.name, call.function.arguments)
                steps.append({"tool": call.function.name, "arguments": call.function.arguments, "result": result})
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        return "I stopped after too many steps. Please ask a more specific question.", steps, messages[1:]
