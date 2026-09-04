"""Z3RO text-to-speech module.

Uses pyttsx3 for instant offline speech. Zero latency, no internet
required.
"""

import pyttsx3


from z3ro.config import config


class TTS:
    """Offline text-to-speech using pyttsx3."""

    def __init__(self):

        self.engine = pyttsx3.init()

        # Slightly faster than default
        self.engine.setProperty(
            "rate",
            config.TTS_RATE,
        )

        # Lower volume so it doesn't blast
        self.engine.setProperty(
            "volume",
            config.TTS_VOLUME,
        )

    def say(self, text: str):
        """Speak text aloud. Blocks until done."""

        if not text:
            return

        try:
            self.engine.say(text)
            self.engine.runAndWait()
        except Exception as e:
            print(f"  [TTS warning] {e}")

    def speak(self, text: str):
        """Speak text aloud (alias for say)."""
        self.say(text)
