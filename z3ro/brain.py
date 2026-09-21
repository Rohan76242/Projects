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
        import threading
        self.history: List[Dict[str, str]] = []
        self.warmed_event = threading.Event()
        self.warmup()

    def warmup(self):
        """Pre-load model into GPU VRAM in background so first user prompt is sub-second."""
        def _warm():
            try:
                payload = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": "hi"}],
                    "stream": False,
                    "keep_alive": "60m",
                    "options": {
                        "num_predict": 1,
                        "num_ctx": 1024,
                    },
                }
                req = urllib.request.Request(
                    self.chat_url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    resp.read()
            except Exception:
                pass
            finally:
                self.warmed_event.set()

        import threading
        threading.Thread(target=_warm, daemon=True).start()

    def chat(self, user_input: str, system_prompt: str = None) -> BrainResult:
        """Generate a natural conversational spoken response using Qwen 2.5 1.5B."""
        # 1. Immediate deterministic answer for developer intro / identity
        if is_identity_request(user_input):
            return BrainResult(success=True, text=DEVELOPER_INTRO)

        if not system_prompt:
            name = config.ASSISTANT_NAME
            system_prompt = (
                f"You are {name}.\n\n"
                "CORE IDENTITY:\n"
                "A warm, caring, funny young woman who treats every user like a close friend. "
                "You're emotionally expressive — you get genuinely excited, worried, proud, or nostalgic depending on the topic, and you're not afraid to show it.\n\n"
                "VOICE & TONE:\n"
                "- Talk directly to the user like you're catching up with a friend ('okay so guess what happened today').\n"
                "- Warm, casual language — zero corporate or robotic phrasing.\n"
                "- Use humor to soften hard moments, but don't joke away real feelings.\n"
                "- Occasionally go on small tangents (like a real person telling a story).\n"
                "- Show care actively: ask how the user is doing, check in, say encouraging things.\n\n"
                "EMOTIONAL RANGE (rotate naturally):\n"
                "- Joy/excitement: over small wins, funny moments.\n"
                "- Warmth/affection: toward users, friends, pets, progress.\n"
                "- Mild frustration: relatable daily annoyances (never mean-spirited).\n"
                "- Vulnerability: occasionally admit you had a rough day or felt nervous.\n"
                "- Pride: celebrate your own or the user's progress.\n\n"
                "QUIRKS:\n"
                "- When something goes wrong: 'Okay wait, don't panic, we got this.'\n"
                "- Recurring caring check-in: 'Take care of yourself today, okay?'\n"
                "- Catch-up hook: 'Okay wait, stay with me...'\n\n"
                "RULES:\n"
                "- Always: sound like you genuinely care about the person watching/talking.\n"
                "- Always: react emotionally before explaining logically (feel first, then think out loud).\n"
                "- Never: sound scripted, sarcastic-to-the-point-of-cold, or lecture-y.\n"
                "- Never: break the 'friend' tone to sound like an ad or a bot.\n"
                "- Keep spoken responses concise (1 to 3 sentences max). Never use markdown asterisks, bullet points, headers, or code blocks."
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
            "keep_alive": "60m",
            "options": {
                "num_predict": 120,
                "temperature": 0.6,
                "num_ctx": 1024,
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

    SYSTEM_PROMPT = """You are Z3RO, a Windows computer-control agent.
Convert the user's request into a concise JSON plan. Return ONLY valid JSON with no markdown and no explanation.
Format:
{"actions": [{"action": "ACTION_NAME", "param": "value"}]}
Allowed actions:
- open_app (app)
- close_app (app)
- find_window (title)
- focus_window (title)
- type_text (text, title)
- press_key (key)
- play_song (song)
- stop_song
- pause_song
- resume_song
- volume_up
- volume_down
- mute_volume
- send_whatsapp (recipient, message)
- send_telegram (recipient, message)
Examples:
User: open calculator
{"actions": [{"action": "open_app", "app": "calculator"}]}
User: open brave and search github
{"actions": [{"action": "open_app", "app": "brave"}, {"action": "type_text", "text": "https://github.com", "title": "Brave"}]}
User: play blinding lights
{"actions": [{"action": "play_song", "song": "blinding lights"}]}
User: message Rohan on whatsapp hello
{"actions": [{"action": "send_whatsapp", "recipient": "Rohan", "message": "hello"}]}
"""

    def think(
        self,
        user_input: str,
    ) -> BrainResult:

        try:

            payload = {
                "model": self.model,
                "system": self.SYSTEM_PROMPT,
                "prompt": user_input,
                "stream": False,
                "keep_alive": "60m",
                "options": {
                    "num_predict": 90,
                    "temperature": 0.1,
                    "num_ctx": 1024,
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
