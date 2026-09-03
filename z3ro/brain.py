import json
import urllib.request
import urllib.error
from dataclasses import dataclass


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen3:1.7b"


SYSTEM_PROMPT = """
You are Z3RO, a Windows computer-control planner.

Convert the user's command into a JSON action plan.

Return ONLY valid JSON.
Do not use markdown.
Do not explain anything.

The JSON format is:

{
  "actions": [
    {
      "action": "action_name",
      "parameters": "..."
    }
  ]
}

Allowed actions:

1. open_app
   Parameters:
   - app: notepad, calculator, paint, explorer, chrome

2. focus_window
   Parameters:
   - title: short visible window title

3. type_text
   Parameters:
   - text: text to type

4. press_key
   Parameters:
   - key: enter, esc, tab, space, backspace, delete,
          up, down, left, right, home, end, pageup, pagedown

5. move_mouse
   Parameters:
   - x: integer screen coordinate
   - y: integer screen coordinate

6. click_mouse
   Parameters:
   - button: left, right, or middle

7. double_click_mouse
   Parameters:
   - no parameters

Examples:

User: open notepad
Output:
{
  "actions": [
    {
      "action": "open_app",
      "app": "notepad"
    }
  ]
}

User: move the mouse to 500 300
Output:
{
  "actions": [
    {
      "action": "move_mouse",
      "x": 500,
      "y": 300
    }
  ]
}

User: click the mouse
Output:
{
  "actions": [
    {
      "action": "click_mouse",
      "button": "left"
    }
  ]
}

User: right click
Output:
{
  "actions": [
    {
      "action": "click_mouse",
      "button": "right"
    }
  ]
}

User: open notepad and type hello
Output:
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
      "text": "hello"
    }
  ]
}

If the user is only asking a normal conversational question, return:

{
  "actions": []
}
"""


@dataclass
class BrainResponse:
    success: bool
    text: str = ""
    error: str = ""


class Brain:

    def think(self, user_input: str) -> BrainResponse:
        raise NotImplementedError


class LocalBrain(Brain):

    def __init__(self):
        self.model = MODEL

    def think(self, user_input: str) -> BrainResponse:

        payload = {
            "model": self.model,
            "system": SYSTEM_PROMPT,
            "prompt": user_input,
            "stream": False,
            "think": False,
        }

        data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            OLLAMA_URL,
            data=data,
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:

            with urllib.request.urlopen(
                request,
                timeout=120,
            ) as response:

                raw_response = response.read().decode("utf-8")

            result = json.loads(raw_response)

            text = result.get("response", "").strip()

            if not text:
                return BrainResponse(
                    success=False,
                    error="Local brain returned an empty response.",
                )

            return BrainResponse(
                success=True,
                text=text,
            )

        except urllib.error.HTTPError as e:

            return BrainResponse(
                success=False,
                error=f"Ollama HTTP error: {e.code}",
            )

        except urllib.error.URLError as e:

            return BrainResponse(
                success=False,
                error=f"Could not connect to Ollama: {e.reason}",
            )

        except Exception as e:

            return BrainResponse(
                success=False,
                error=str(e),
            )


if __name__ == "__main__":

    print("================================")
    print("          Z3RO BRAIN")
    print("================================")
    print()
    print(f"Model: {MODEL}")
    print("Runtime: Ollama")
    print()

    brain = LocalBrain()

    while True:

        user_input = input("You: ").strip()

        if user_input.lower() == "exit":
            break

        if not user_input:
            continue

        response = brain.think(user_input)

        if response.success:

            print()
            print("RAW BRAIN OUTPUT:")
            print(response.text)
            print()

        else:

            print()
            print("BRAIN ERROR:")
            print(response.error)
            print()