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
                    task = asyncio.create_task(self._edge_synthesize_and_play(text))
                    # Wait for task
                    import concurrent.futures
                    future = asyncio.run_coroutine_threadsafe(self._edge_synthesize_and_play(text), loop)
                    future.result(timeout=15)
                else:
                    loop.run_until_complete(self._edge_synthesize_and_play(text))
                return
            except Exception as e:
                # Fall back to offline voice if network is unavailable
                pass

        # Offline fallback
        self._fallback_offline(text)

    def speak(self, text: str):
        """Speak text aloud (alias for say)."""
        self.say(text)
