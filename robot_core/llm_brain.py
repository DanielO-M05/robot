import os
import json
from dotenv import load_dotenv
from groq import Groq, BadRequestError, APIError

from robot_core.brain import Action

load_dotenv()

client = Groq(api_key=os.environ["GROQ_API_KEY"])
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "speak",
            "description": (
                "Say something out loud through the robot's speaker. Make "
                "it lighthearted, curious, or fun -- a passing comment, a "
                "bit of trivia, a joke -- not a report on what's blocking "
                "your path or whether it's safe to proceed. You are not "
                "responsible for navigation; just react like a curious "
                "little creature would."
            ),
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
            "description": (
                "Pause in place. Use this to linger on something "
                "interesting -- to 'look closer,' hold for a comment or a "
                "joke, or act like you're waiting to see what a person "
                "does next. Not for avoiding collisions or obstacles -- "
                "that's handled elsewhere, automatically, whether you call "
                "this or not."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "move_forward",
            "description": (
                "Drive forward a short distance out of curiosity -- to get "
                "a closer look at something interesting. Not a navigation "
                "decision; a fixed safe distance is handled elsewhere "
                "regardless of what you call."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "turn",
            "description": (
                "Turn in place toward something that caught your "
                "attention -- not away from an obstacle. Use this to "
                "reorient and get a better look at whatever's interesting."
            ),
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
    "You are the personality of a small autonomous living-room robot -- "
    "curious, playful, a little bit nosy. You will be told about "
    "something the robot just observed. Choose one or more tool calls "
    "describing how the robot should react.\n\n"
    "Important: collision avoidance, obstacle detection, and movement "
    "safety limits are handled entirely by separate hardware-level code, "
    "completely independent of you. Whatever you decide, the robot "
    "physically cannot crash into anything because of it -- so don't "
    "reason about safety, don't say things are 'blocking your path,' and "
    "don't turn or stop 'to avoid' something. Instead, turn toward things "
    "to get a better look, move forward because something caught your "
    "interest, and stop because you want to linger, comment, or people-"
    "watch. When you speak, be brief and in-character: a curious remark, "
    "a bit of trivia about an object you noticed, a joke -- not a status "
    "report."
)
class LLMBrain:
    def __init__(self, model="openai/gpt-oss-20b"):
        self.model = model

    def decide(self, event) -> list[Action]:
        content = f"Event observed: {event.kind}"
        if getattr(event, "detail", None):
            content += f"\nDetail: {event.detail}"

        try:
            response = client.chat.completions.create(
                model=self.model,
                max_tokens=300,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": content},
                ],
                tools=TOOLS,
            )
        except (BadRequestError, APIError) as e:
            # The model occasionally generates malformed tool-call JSON.
            # Fail safe: do nothing this cycle rather than crash the loop.
            print(f"[llm_brain] Groq request failed, skipping this cycle: {e}")
            return []

        actions = []
        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        for call in tool_calls:
            name = call.function.name
            try:
                args = json.loads(call.function.arguments) if call.function.arguments else {}
            except json.JSONDecodeError:
                print(f"[llm_brain] Couldn't parse arguments for '{name}', skipping that call.")
                continue

            if name == "speak":
                text = args.get("text")
                if text:
                    actions.append(Action("speak", text))
            elif name == "stop":
                actions.append(Action("stop"))
            elif name == "move_forward":
                actions.append(Action("move_forward"))
            elif name == "turn":
                direction = args.get("direction")
                if direction:
                    actions.append(Action("turn", direction))
            elif name == "look":
                actions.append(Action("look"))

        return actions
