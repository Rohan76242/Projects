"""Z3RO speech-to-text module.

Records a short command from the microphone after the wake word
is detected, then transcribes it with faster-whisper.
"""

import numpy as np
import sounddevice as sd
import soundfile as sf

from faster_whisper import WhisperModel
from z3ro.config import config


# How long to record the user's command (seconds)
RECORD_SECONDS = 4

SAMPLE_RATE = 16000

# Temp file for the recorded audio
AUDIO_PATH = "z3ro_command.wav"


class STT:
    """Speech-to-text using faster-whisper."""

    def __init__(self):

        print(
            "  Loading Whisper (small, int8)..."
        )

        self.model = WhisperModel(
            "small",
            device="cpu",
            compute_type="int8",
        )

        print(
            "  Whisper ready."
        )

    def listen(
        self,
        seconds: float = RECORD_SECONDS,
    ) -> str:
        """Record from mic and return transcribed text."""

        print(
            f"  Listening for {seconds}s..."
        )

        audio = sd.rec(
            int(seconds * SAMPLE_RATE),
            device=config.MIC_DEVICE_INDEX,
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
        )

        sd.wait()

        # Flatten to 1D
        audio_flat = audio[:, 0]

        # Skip if silence
        if np.max(np.abs(audio_flat)) < 0.01:
            return ""

        sf.write(
            AUDIO_PATH,
            audio_flat,
            SAMPLE_RATE,
        )

        segments, _ = self.model.transcribe(
            AUDIO_PATH,
            language="en",
            vad_filter=True,
            beam_size=5,
        )

        text = " ".join(
            segment.text
            for segment in segments
        ).strip()

        return text
