import json
import urllib.request
from dataclasses import dataclass, field
from typing import List, Dict

from z3ro.app_catalog import app_catalog_prompt
from z3ro.config import config


@dataclass
class BrainResult:
    success: bool
    text: str = ""
    error: str = ""


class LocalBrain:
    """Z3RO / SOBIA local reasoning and conversational chat brain."""

    def __init__(self, model: str = None, host: str = None):
        self.model = model or config.BRAIN_MODEL
        self.host = host or config.OLLAMA_HOST
        self.generate_url = f"{self.host}/api/generate"
        self.chat_url = f"{self.host}/api/chat"
        self.history: List[Dict[str, str]] = []

    def chat(self, user_input: str, system_prompt: str = None) -> BrainResult:
        """Generate a natural conversational spoken response using Qwen 2.5 1.5B."""
        if not system_prompt:
            name = config.ASSISTANT_NAME
            system_prompt = (
                f"You are {name}, a helpful, intelligent, and friendly desktop voice assistant. "
                "You communicate naturally with the user through spoken conversation. "
                "Keep your answers concise, warm, helpful, and natural (1 to 3 sentences max). "
                "Never use markdown formatting, bullet points, asterisks, or code blocks in spoken responses."
            )

        messages = [{"role": "system", "content": system_prompt}]
        # Keep last 6 conversational turns for context
        for turn in self.history[-6:]:
            messages.append(turn)
        messages.append({"role": "user", "content": user_input})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": 250,
                "temperature": 0.7,
            },
        }

        try:
            req = urllib.request.Request(
                self.chat_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                reply = data.get("message", {}).get("content", "").strip()

            if not reply:
                return BrainResult(success=False, error="Empty response from chat model")

            # Clean reply so it speaks naturally without asterisks or markdown
            clean_reply = reply.replace("*", "").replace("`", "").replace("#", "").strip()

            # Record in history
            self.history.append({"role": "user", "content": user_input})
            self.history.append({"role": "assistant", "content": clean_reply})

            return BrainResult(success=True, text=clean_reply)

        except Exception as e:
            return BrainResult(success=False, error=str(e))

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
send_whatsapp
open_whatsapp
send_telegram
open_telegram
play_song

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
11. Use send_whatsapp to send a message on WhatsApp.
12. Use open_whatsapp to open the WhatsApp app.
13. Use send_telegram to send a message on Telegram.
14. Use open_telegram to open the Telegram app.
15. Use play_song to play a song, music, or video on YouTube.
16. Keep plans short.
17. Return JSON only.
18. Do not include markdown.
19. Do not include explanations.

Examples:

User:
play a song

JSON:
{
    "actions": [
        {
            "action": "play_song",
            "song": "top hits"
        }
    ]
}

User:
play despacito

JSON:
{
    "actions": [
        {
            "action": "play_song",
            "song": "despacito"
        }
    ]
}

User:
play believer on youtube

JSON:
{
    "actions": [
        {
            "action": "play_song",
            "song": "believer"
        }
    ]
}

User:
open youtube and play a song

JSON:
{
    "actions": [
        {
            "action": "play_song",
            "song": "top hits"
        }
    ]
}

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
send whatsapp to Rohan hello how are you

JSON:
{
    "actions": [
        {
            "action": "send_whatsapp",
            "recipient": "Rohan",
            "message": "hello how are you"
        }
    ]
}

User:
send telegram to @alex meeting at 5

JSON:
{
    "actions": [
        {
            "action": "send_telegram",
            "recipient": "@alex",
            "message": "meeting at 5"
        }
    ]
}

User:
open youtube

JSON:
{
    "actions": [
        {
            "action": "open_app",
            "app": "youtube"
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
                "model": self.model,
                "system": (
                    self.SYSTEM_PROMPT
                    + "\n\n"
                    + app_catalog_prompt()
                ),
                "prompt": user_input,
                "stream": False,
                "options": {
                    "num_predict": config.NUM_PREDICT,
                    "num_ctx": config.NUM_CTX,
                },
            }

            data = json.dumps(
                payload
            ).encode("utf-8")

            request = urllib.request.Request(
                self.generate_url,
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
