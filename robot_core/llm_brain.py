import os
import json
from dotenv import load_dotenv
from groq import Groq

from robot_core.brain import Action

load_dotenv()

client = Groq(api_key=os.environ["GROQ_API_KEY"])

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "speak",
            "description": "Say something out loud through the robot's speaker.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "stop",
            "description": "Stop all motor movement immediately.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_forward",
            "description": "Drive forward for a short, safe duration.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn",
            "description": "Turn in place.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["left", "right"]}
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "look",
            "description": "Look around using the camera and describe what's seen.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

SYSTEM_PROMPT = (
    "You are the decision-making brain of a small autonomous living-room "
    "robot. You will be told about an event the robot just observed. "
    "Choose one or more tool calls describing how the robot should react. "
    "Be brief and in-character when speaking -- short, natural reactions, "
    "not long explanations. Low-level safety (obstacle avoidance, movement "
    "limits) is handled elsewhere; you only decide *intent*."
)


class LLMBrain:
    def __init__(self, model="openai/gpt-oss-20b"):
        self.model = model

    def decide(self, event) -> list[Action]:
        content = f"Event observed: {event.kind}"
        if getattr(event, "detail", None):
            content += f"\nDetail: {event.detail}"

        response = client.chat.completions.create(
            model=self.model,
            max_tokens=300,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": content},
            ],
            tools=TOOLS,
        )

        actions = []
        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        for call in tool_calls:
            name = call.function.name
            args = json.loads(call.function.arguments) if call.function.arguments else {}

            if name == "speak":
                actions.append(Action("speak", args["text"]))
            elif name == "stop":
                actions.append(Action("stop"))
            elif name == "move_forward":
                actions.append(Action("move_forward"))
            elif name == "turn":
                actions.append(Action("turn", args["direction"]))
            elif name == "look":
                actions.append(Action("look"))

        return actions
