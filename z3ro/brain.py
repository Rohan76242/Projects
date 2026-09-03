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

Your response MUST always have this structure:

{
  "actions": []
}

Each item in "actions" must contain exactly one supported action.

AVAILABLE ACTIONS:

Open an application:
{
  "action": "open_app",
  "app": "notepad"
}

Focus a visible window:
{
  "action": "focus_window",
  "title": "Notepad"
}

Type text:
{
  "action": "type_text",
  "text": "Hello bro"
}

Press one keyboard key:
{
  "action": "press_key",
  "key": "enter"
}

For normal conversation, use:
{
  "actions": []
}

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

IMPORTANT:
- Use the minimum number of actions required.
- Maximum 5 actions.
- Do not invent actions.
- Do not execute commands.
- Do not use shell commands.
- Do not include explanations outside JSON.

Examples:

User: Open Notepad

{
  "actions": [
    {
      "action": "open_app",
      "app": "notepad"
    }
  ]
}

User: Open Notepad and type Hello from Z3RO

{
  "actions": [
    {
      "action": "open_app",
      "app": "notepad"
    },
    {
      "action": "focus_window",
      "title": "Notepad"
    },
    {
      "action": "type_text",
      "text": "Hello from Z3RO"
    }
  ]
}

User: Focus ChatGPT

{
  "actions": [
    {
      "action": "focus_window",
      "title": "ChatGPT"
    }
  ]
}

User: Press Enter

{
  "actions": [
    {
      "action": "press_key",
      "key": "enter"
    }
  ]
}

User: Hello

{
  "actions": []
}
"""


@dataclass
class BrainResponse:
    text: str
    success: bool = True
    error: Optional[str] = None


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
                headers={
                    "Content-Type": "application/json"
                },
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

    if not response.success:

        print("ERROR:", response.error)

    else:

        print()
        print("RAW BRAIN OUTPUT:")
        print(response.text)