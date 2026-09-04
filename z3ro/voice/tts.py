"""Z3RO text-to-speech module.

Uses pyttsx3 for instant offline speech. Zero latency, no internet
required.
"""

import pyttsx3


class TTS:
    """Offline text-to-speech using pyttsx3."""

    def __init__(self):

        self.engine = pyttsx3.init()

        # Slightly faster than default
        self.engine.setProperty(
            "rate",
            180,
        )

        # Lower volume so it doesn't blast
        self.engine.setProperty(
            "volume",
            0.9,
        )

    def say(self, text: str):
        """Speak text aloud. Blocks until done."""

        if not text:
            return

        self.engine.say(text)
        self.engine.runAndWait()
