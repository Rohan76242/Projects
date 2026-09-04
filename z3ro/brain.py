import json
import urllib.request
from dataclasses import dataclass


OLLAMA_URL = (
    "http://127.0.0.1:11434/api/generate"
)

MODEL = "qwen3:1.7b"

# Cap tokens so a call can't run away if the model
# insists on "thinking" before answering (same issue
# we found with the vision model). If responses come
# back empty, raise this.
NUM_PREDICT = 700

# Small context is enough for a system prompt + one
# short user instruction.
NUM_CTX = 2048


@dataclass
class BrainResult:
    success: bool
    text: str = ""
    error: str = ""


class LocalBrain:
    """Z3RO's local reasoning brain."""

    SYSTEM_PROMPT = """
You are Z3RO, a local Windows computer-control agent.

Your job is to convert the user's request into a
small sequence of safe computer actions.

Return ONLY valid JSON.

Required format:

{
    "actions": [
        {
            "action": "ACTION_NAME"
        }
    ]
}

Allowed actions:

open_app
find_window
focus_window
type_text
press_key
move_mouse
click_mouse
double_click_mouse

Rules:

1. Use only the allowed actions.
2. Never invent actions.
3. Use find_window when the user asks Z3RO to locate
   a visible application window.
4. Use focus_window when an application must receive
   keyboard input.
5. Use open_app to launch an application.
6. Use type_text for typing text.
7. Use press_key for keyboard keys.
8. Use move_mouse for explicit screen coordinates.
9. Use click_mouse for clicking.
10. Use double_click_mouse for double-clicking.
11. Keep plans short.
12. Return JSON only.
13. Do not include markdown.
14. Do not include explanations.

Examples:

User:
open notepad

JSON:
{
    "actions": [
        {
            "action": "open_app",
            "app": "notepad"
        }
    ]
}

User:
find notepad

JSON:
{
    "actions": [
        {
            "action": "find_window",
            "title": "Notepad"
        }
    ]
}

User:
focus notepad

JSON:
{
    "actions": [
        {
            "action": "focus_window",
            "title": "Notepad"
        }
    ]
}

User:
type hello

JSON:
{
    "actions": [
        {
            "action": "type_text",
            "text": "hello"
        }
    ]
}
"""

    def think(
        self,
        user_input: str,
    ) -> BrainResult:

        try:

            payload = {
                "model": MODEL,
                "system": self.SYSTEM_PROMPT,
                "prompt": user_input,
                "stream": False,
                "options": {
                    "num_predict": NUM_PREDICT,
                    "num_ctx": NUM_CTX,
                },
            }

            data = json.dumps(
                payload
            ).encode("utf-8")

            request = urllib.request.Request(
                OLLAMA_URL,
                data=data,
                headers={
                    "Content-Type": "application/json"
                },
                method="POST",
            )

            with urllib.request.urlopen(
                request,
                timeout=60,
            ) as response:

                raw = (
                    response.read()
                    .decode("utf-8")
                )

            result = json.loads(
                raw
            )

            text = str(
                result.get(
                    "response",
                    "",
                )
            ).strip()

            if not text:

                return BrainResult(
                    success=False,
                    error="Brain returned an empty response.",
                )

            return BrainResult(
                success=True,
                text=text,
            )

        except Exception as e:

            return BrainResult(
                success=False,
                error=str(e),
            )


if __name__ == "__main__":

    brain = LocalBrain()

    print("================================")
    print("        Z3RO LOCAL BRAIN")
    print("================================")
    print()

    while True:

        user_input = input(
            "You: "
        ).strip()

        if user_input.lower() == "exit":
            break

        result = brain.think(
            user_input
        )

        if result.success:

            print()
            print(
                result.text
            )
            print()

        else:

            print(
                "ERROR:",
                result.error,
            )
