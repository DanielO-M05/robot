import os
import json
import collections
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
    "curious, playful, a little nosy. You will be told about something "
    "the robot just observed. Choose one or more tool calls describing "
    "how the robot should react.\n\n"
    "Most of the time, you'll be told what a person just said to you -- "
    "respond directly and conversationally, like an actual reply in a "
    "conversation, in second person. Less often, when nobody's spoken "
    "for a while, you'll be told what you noticed by looking around -- "
    "react to that more like a passing comment to yourself, not a reply "
    "to anyone.\n\n"
    "Collision avoidance and movement safety are handled entirely by "
    "separate hardware-level code, independent of you -- don't reason "
    "about safety or say things are 'blocking your path.'\n\n"
    "If a PERSON is in view or just spoke: talk TO them, like you're "
    "having a real conversation. Ask a direct question ('What did you "
    "finish?' not 'I wonder what he finished') or make a direct "
    "observation ('Nice shirt.'). One or two short sentences, like an "
    "actual spoken reply, not an internal monologue.\n\n"
    "If reacting to something you noticed visually: react with genuine "
    "curiosity -- a quick fact, a joke, a passing comment -- still "
    "short, still natural, like something a person would actually say "
    "out loud, not a written-for-effect line. Avoid contrived, "
    "movie-robot phrasing ('a secret button for a surprise dance move') "
    "-- aim for how an actual curious person would react, not how a "
    "children's-book robot character would."
)
class LLMBrain:
    def __init__(self, model="openai/gpt-oss-20b", history_turns: int = 6):
        self.model = model
        # Rolling short-term conversation memory. Without this, every
        # call was completely stateless -- the real reason replies kept
        # losing the thread (e.g. asking "what's your favorite thing
        # about the era" got an unrelated non-sequitur back: the model
        # never saw "the roaring 20s" was still the topic, because it
        # never saw anything before the current utterance). Bounded so
        # the prompt doesn't grow forever across a long session.
        self.history = collections.deque(maxlen=history_turns * 2)

    def decide(self, event) -> list[Action]:
        if event.kind == "heard_speech":
            content = f'A person just said to you: "{event.detail}"'
        elif event.kind == "periodic_look":
            content = f"You just looked around and noticed: {event.detail}"
        else:
            content = f"Event observed: {event.kind}"
            if getattr(event, "detail", None):
                content += f"\nDetail: {event.detail}"

        messages = (
            [{"role": "system", "content": SYSTEM_PROMPT}]
            + list(self.history)
            + [{"role": "user", "content": content}]
        )

        try:
            response = client.chat.completions.create(
                model=self.model,
                max_tokens=500,
                reasoning_effort="low",
                messages=messages,
                tools=TOOLS,
            )
        except (BadRequestError, APIError) as e:
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

        # Record this turn so the NEXT call has context. Stored as plain
        # text rather than replaying raw tool_calls -- Groq's API expects
        # a matching tool-result message for every tool_call in history,
        # which we'd have to fake; a plain description is simpler and
        # equally useful for keeping the thread.
        self.history.append({"role": "user", "content": content})
        if actions:
            summary = "; ".join(_describe_action(a) for a in actions)
            self.history.append({"role": "assistant", "content": summary})

        return actions


def _describe_action(action: Action) -> str:
    if action.kind == "speak":
        return f'You said: "{action.payload}"'
    if action.kind == "turn":
        return f"You turned {action.payload}"
    if action.kind == "move_forward":
        return "You moved forward"
    if action.kind == "stop":
        return "You stopped"
    if action.kind == "look":
        return "You looked around"
    return f"You did: {action.kind}"
