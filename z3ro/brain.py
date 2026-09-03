import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen3:1.7b"


SYSTEM_PROMPT = """
You are Z3RO, a Windows computer-control agent.

Return ONLY valid JSON.
Never use markdown.
Never explain your reasoning.
Never expose internal reasoning.

AVAILABLE ACTIONS:

Open an application:
{"action":"open_app","app":"notepad"}

Focus a visible window:
{"action":"focus_window","title":"ChatGPT"}

Type text:
{"action":"type_text","text":"Hello bro"}

Press one keyboard key:
{"action":"press_key","key":"enter"}

Normal conversation:
{"action":"none","response":"Hello. I'm Z3RO."}

Unsupported request:
{"action":"none","response":"I can't perform that action yet."}

SUPPORTED APPS:
notepad
calculator
paint
explorer
chrome

SUPPORTED KEYS:
enter
esc
tab
space
backspace
delete
up
down
left
right
home
end
pageup
pagedown

Examples:

User: Open Notepad
{"action":"open_app","app":"notepad"}

User: Focus ChatGPT
{"action":"focus_window","title":"ChatGPT"}

User: Type Hello bro
{"action":"type_text","text":"Hello bro"}

User: Press Enter
{"action":"press_key","key":"enter"}

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
    title: Optional[str] = None
    text: Optional[str] = None
    key: Optional[str] = None
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

            with urllib.request.urlopen(
                request,
                timeout=120,
            ) as response:

                data = json.loads(
                    response.read().decode("utf-8")
                )

            text = data.get("response", "").strip()

            if not text:

                return BrainResponse(
                    text="",
                    success=False,
                    error="Ollama returned an empty response.",
                )

            return BrainResponse(
                text=text,
                success=True,
            )

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

        text = response.text.strip()

        # Remove accidental markdown fences.
        if text.startswith("```"):

            lines = text.splitlines()

            if lines:
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            text = "\n".join(lines).strip()

        data = json.loads(text)

        return ToolDecision(
            action=data.get("action", "none"),
            app=data.get("app"),
            title=data.get("title"),
            text=data.get("text"),
            key=data.get("key"),
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

    print(
        json.dumps(
            {
                "action": decision.action,
                "app": decision.app,
                "title": decision.title,
                "text": decision.text,
                "key": decision.key,
                "response": decision.response,
            },
            indent=2,
        )
    )