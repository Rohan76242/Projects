import json
import urllib.request
from dataclasses import dataclass, field
from typing import List, Dict

import re
from z3ro.app_catalog import app_catalog_prompt
from z3ro.config import config


DEVELOPER_INTRO = (
    "SOBIA was created by **Rohan** — a developer passionate about technology, "
    "artificial intelligence, and building systems that make everyday life simpler.\n\n"
    "What started as an idea became SOBIA: a personal AI designed to understand, "
    "assist, and grow alongside its creator.\n\n"
    "**Built with curiosity. Driven by innovation.**"
)

IDENTITY_PATTERNS = (
    "who are you",
    "who r u",
    "who created you",
    "who made you",
    "who is your creator",
    "who is your developer",
    "who is the developer",
    "who built you",
    "who designed you",
    "intro of the developer",
    "intro of developer",
    "developer intro",
    "tell me about the developer",
    "tell me about your developer",
    "tell me about your creator",
    "tell me about yourself",
    "who programmed you",
    "what is sobia",
    "who is sobia",
    "introduce yourself",
)


def is_identity_request(text: str) -> bool:
    """Check if the user is asking about the assistant's identity, creator, or developer."""
    if not text:
        return False
    cleaned = re.sub(r"[^\w\s]", "", text.lower()).strip()
    if any(p in cleaned for p in IDENTITY_PATTERNS):
        return True
    words = set(cleaned.split())
    if "who" in words and any(w in words for w in ("you", "u", "sobia", "z3ro")):
        return True
    if any(w in words for w in ("developer", "creator")) and any(
        w in words for w in ("who", "intro", "introduction", "tell", "about", "your", "the")
    ):
        return True
    return False


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
        # 1. Immediate deterministic answer for developer intro / identity
        if is_identity_request(user_input):
            return BrainResult(success=True, text=DEVELOPER_INTRO)

        if not system_prompt:
            name = config.ASSISTANT_NAME
            system_prompt = (
                f"You are {name} (SOBIA), an intelligent desktop AI assistant created by Rohan. "
                "Rohan is a developer passionate about technology, artificial intelligence, and building systems that make everyday life simpler. "
                "What started as an idea became SOBIA: a personal AI designed to understand, assist, and grow alongside its creator. "
                "Built with curiosity. Driven by innovation. "
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
pause_song
resume_song
stop_song
next_song
previous_song
change_video
volume_up
volume_down
mute_volume

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
16. Use stop_song to stop music, video, or song playback.
17. Use pause_song to pause playing audio or video.
18. Use resume_song to resume paused playback.
19. Use change_video or next_song to change video or skip song.
20. Use volume_up to increase volume or turn volume up.
21. Use volume_down to decrease volume or turn volume down.
22. Use mute_volume to mute or unmute sound.
23. Keep plans short.
24. Return JSON only.
25. Do not include markdown.
26. Do not include explanations.

Examples:

User:
turn volume up

JSON:
{
    "actions": [
        {
            "action": "volume_up"
        }
    ]
}

User:
turn volume down

JSON:
{
    "actions": [
        {
            "action": "volume_down"
        }
    ]
}

User:
stop song

JSON:
{
    "actions": [
        {
            "action": "stop_song"
        }
    ]
}

User:
change the video

JSON:
{
    "actions": [
        {
            "action": "change_video"
        }
    ]
}

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
