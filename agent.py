import json
import os

from openai import OpenAI

from database import create_support_ticket, get_customer_orders, get_order_status


TOOLS = [
    {
        "type": "function",
        "name": "get_order_status",
        "description": "Look up the status and estimated delivery date of an order.",
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"}
            },
            "required": ["order_id"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "get_customer_orders",
        "description": "List orders belonging to the current authenticated customer.",
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "create_support_ticket",
        "description": "Create an open support ticket for the current customer.",
        "parameters": {
            "type": "object",
            "properties": {
                "issue": {"type": "string"}
            },
            "required": ["issue"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


class SupportAgent:
    def __init__(self, customer_id, model):
        self.customer_id = customer_id
        self.model = model
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def _execute(self, name, arguments):
        if name == "get_order_status":
            return get_order_status(arguments["order_id"])
        if name == "get_customer_orders":
            return get_customer_orders(self.customer_id)
        if name == "create_support_ticket":
            return create_support_ticket(self.customer_id, arguments["issue"])
        raise ValueError(f"Unknown tool: {name}")

    def run(self, user_message):
        instructions = f"""You are a concise customer-support assistant.
The authenticated customer is {self.customer_id}.
Never expose data belonging to another customer.
Use tools whenever order or ticket information is needed.
Do not claim an action happened unless the tool returned success.
"""

        input_items = [{"role": "user", "content": user_message}]
        tools_used = []

        for _ in range(5):
            response = self.client.responses.create(
                model=self.model,
                instructions=instructions,
                tools=TOOLS,
                input=input_items,
            )

            input_items += response.output
            function_calls = [item for item in response.output if item.type == "function_call"]

            if not function_calls:
                return response.output_text, tools_used

            for call in function_calls:
                args = json.loads(call.arguments)
                result = self._execute(call.name, args)
                tools_used.append(call.name)
                input_items.append({
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(result),
                })

        return "I could not complete the request safely.", tools_used
