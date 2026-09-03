import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen3:1.7b"


SYSTEM_PROMPT = """
You are Z3RO, a Windows computer-control agent.

Your job is to decide whether the user wants a supported tool action.

AVAILABLE TOOLS:
- open_app

SUPPORTED APPS:
- notepad
- calculator
- paint
- explorer
- chrome

OUTPUT RULES:
Return ONLY valid JSON.
Never use markdown.
Never explain your reasoning.

For an app-opening request:
{"action":"open_app","app":"APP_NAME"}

For normal conversation:
{"action":"none","response":"YOUR_RESPONSE"}

If the requested action is unsupported:
{"action":"none","response":"I can't perform that action yet."}

Examples:

User: Open Notepad
{"action":"open_app","app":"notepad"}

User: Launch Chrome
{"action":"open_app","app":"chrome"}

User: Hello
{"action":"none","response":"Hello. I'm Z3RO."}
"""


@dataclass
class BrainResponse:
    text: str
    success: bool = True
    error: Optional[str] = None


@dataclass
class ToolDecision:
    action: str
    app: Optional[str] = None
    response: Optional[str] = None


class Brain:
    def think(self, prompt: str) -> BrainResponse:
        raise NotImplementedError


class LocalBrain(Brain):

    def __init__(self, model: str = MODEL):
        self.model = model

    def think(self, prompt: str) -> BrainResponse:

        payload = {
            "model": self.model,
            "system": SYSTEM_PROMPT,
            "prompt": prompt,
            "stream": False,
            "think": False,
        }

        try:
            request = urllib.request.Request(
                OLLAMA_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))

            text = data.get("response", "").strip()

            if not text:
                return BrainResponse(
                    text="",
                    success=False,
                    error="Ollama returned an empty response.",
                )

            return BrainResponse(text=text)

        except urllib.error.HTTPError as e:
            return BrainResponse(
                text="",
                success=False,
                error=f"Ollama HTTP {e.code}: {e.reason}",
            )

        except urllib.error.URLError as e:
            return BrainResponse(
                text="",
                success=False,
                error=f"Could not connect to Ollama: {e.reason}",
            )

        except Exception as e:
            return BrainResponse(
                text="",
                success=False,
                error=str(e),
            )


def parse_decision(response: BrainResponse) -> ToolDecision:

    if not response.success:
        return ToolDecision(
            action="none",
            response=response.error,
        )

    try:
        data = json.loads(response.text)

        return ToolDecision(
            action=data.get("action", "none"),
            app=data.get("app"),
            response=data.get("response"),
        )

    except json.JSONDecodeError:
        return ToolDecision(
            action="none",
            response="I couldn't understand the requested action.",
        )


if __name__ == "__main__":

    brain = LocalBrain()

    print("================================")
    print("       Z3RO BRAIN ONLINE")
    print("================================")
    print(f"Model: {MODEL}")
    print("Runtime: Ollama")
    print()

    user_input = input("You: ")

    response = brain.think(user_input)
    decision = parse_decision(response)

    print()
    print("Decision:")
    print(json.dumps({
        "action": decision.action,
        "app": decision.app,
        "response": decision.response,
    }, indent=2))