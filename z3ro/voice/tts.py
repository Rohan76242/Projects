"""Z3RO / SOBIA Text-To-Speech Module.

Provides human-like, studio-quality speech using Microsoft Edge Female Neural TTS
(e.g. en-US-AriaNeural) with automatic offline pyttsx3 fallback.
"""

import io
import asyncio
import sounddevice as sd
import soundfile as sf
import pyttsx3

from z3ro.config import config


import re

def clean_text_for_speech(text: str) -> str:
    """Sanitize text before TTS speech synthesis.

    - Removes file paths like C:\\... or (C:\\...)
    - Removes emojis and unicode symbols
    - Removes codeblocks (```...```) and backticks
    - Removes quotation marks
    - Removes URLs
    - Removes redundant low-level action confirmations (e.g. 'Clicked left mouse button')
    """
    if not text:
        return ""

    # 1. Remove markdown code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    # 2. Remove inline code backticks
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # 3. Remove parenthesized paths: e.g. (C:\Program Files\...) or (C:/...)
    text = re.sub(r"\([A-Za-z]:[^\)]*\)", "", text)
    # 4. Remove standalone paths: C:\...
    text = re.sub(r"[A-Za-z]:\\[^\s,;]+", "", text)
    # 5. Remove URLs
    text = re.sub(r"https?://\S+", "", text)
    # 6. Remove emojis and unicode symbols
    emoji_pattern = re.compile(
        r"[\U00010000-\U0010ffff]"
        r"|[\u2600-\u27bf]"
        r"|[\u2300-\u23ff]"
        r"|[\u2b50-\u2b55]"
        r"|[\u200d\uFE0F\uFE0E]",
        flags=re.UNICODE,
    )
    text = emoji_pattern.sub("", text)
    # 7. Remove markdown formatting like **, *, ##, __, ~~
    text = re.sub(r"[*_#~>]+", " ", text)
    # 8. Remove quotes: ", ', “, ”, ‘, ’
    text = re.sub(r'["\'“”‘’«»`]', "", text)
    # 9. Clean up redundant mouse / low-level debug chatter from speech
    text = re.sub(
        r"\b(Clicked left mouse button|Clicked right mouse button|Moved mouse to \(\d+,\s*\d+\))\b\.?",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # 10. Normalize whitespace and punctuation
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([.,!?])", r"\1", text)
    text = re.sub(r"([.,!?]){2,}", r"\1", text)
    return text


class TTS:
    """Natural neural text-to-speech with offline fallback."""

    def __init__(self, voice: str = None):
        self.voice = voice or config.TTS_VOICE
        self.rate = config.TTS_RATE_EDGE
        self.engine_type = config.TTS_ENGINE

        # Initialize offline fallback engine
        self._offline_engine = None
        try:
            self._offline_engine = pyttsx3.init()
            self._offline_engine.setProperty("rate", config.TTS_RATE)
            self._offline_engine.setProperty("volume", config.TTS_VOLUME)
        except Exception as e:
            pass

    async def _edge_synthesize_and_play(self, text: str):
        """Synthesize neural speech using Edge TTS and play via sounddevice."""
        import edge_tts

        communicate = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
        )

        audio_buffer = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_buffer.write(chunk["data"])

        audio_buffer.seek(0)
        data, sample_rate = sf.read(audio_buffer, dtype="float32")
        sd.play(data, sample_rate)
        sd.wait()

    def _fallback_offline(self, text: str):
        """Speak using offline pyttsx3."""
        if self._offline_engine:
            try:
                self._offline_engine.say(text)
                self._offline_engine.runAndWait()
            except Exception as e:
                print(f"  [TTS offline error] {e}")

    def say(self, text: str):
        """Speak text aloud. Uses Microsoft Edge Neural TTS, with offline fallback."""
        if not text:
            return

        # Sanitize text so it sounds natural, clean, and never speaks file paths or formatting
        clean_text = clean_text_for_speech(text)
        if not clean_text:
            return

        # Attempt Microsoft Edge Neural TTS
        if self.engine_type == "edge":
            try:
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                if loop.is_running():
                    # If called from an already running asyncio loop
                    task = asyncio.create_task(self._edge_synthesize_and_play(clean_text))
                    import concurrent.futures
                    future = asyncio.run_coroutine_threadsafe(self._edge_synthesize_and_play(clean_text), loop)
                    future.result(timeout=15)
                else:
                    loop.run_until_complete(self._edge_synthesize_and_play(clean_text))
                return
            except Exception as e:
                # Fall back to offline voice if network is unavailable
                pass

        # Offline fallback
        self._fallback_offline(clean_text)

    def speak(self, text: str):
        """Speak text aloud (alias for say)."""
        self.say(text)

