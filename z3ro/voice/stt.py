"""Z3RO speech-to-text module.

Records and transcribes speech using faster-whisper.
"""

from typing import Union
import os
import numpy as np
import sounddevice as sd
import soundfile as sf

from faster_whisper import WhisperModel
from z3ro.config import config


# How long to record the user's command (seconds)
RECORD_SECONDS = 4

SAMPLE_RATE = config.AUDIO_SAMPLE_RATE

# Temp file for recorded audio if writing to disk
AUDIO_PATH = "z3ro_command.wav"


class STT:
    """Speech-to-text using faster-whisper."""

    def __init__(self):
        print(f"  Loading Whisper ({config.STT_MODEL_SIZE}, {config.STT_COMPUTE_TYPE})...")

        self.model = WhisperModel(
            config.STT_MODEL_SIZE,
            device=config.STT_DEVICE,
            compute_type=config.STT_COMPUTE_TYPE,
        )

        print("  Whisper ready.")

    def transcribe(
        self,
        audio: Union[np.ndarray, str],
        sample_rate: int = SAMPLE_RATE,
        language: str = "en",
    ) -> str:
        """Transcribe audio samples (numpy array) or an audio file path.
        
        Args:
            audio: 1D numpy array of float32 samples, or path to a .wav audio file.
            sample_rate: Audio sample rate in Hz (default 16000).
            language: Spoken language code (default 'en').

        Returns:
            Transcribed text string.
        """
        # If a file path is provided
        if isinstance(audio, str):
            if not os.path.isfile(audio):
                return ""
            segments, _ = self.model.transcribe(
                audio,
                language=language,
                vad_filter=True,
                beam_size=5,
            )
            return " ".join(seg.text for seg in segments).strip()

        # If a numpy array is provided
        if not isinstance(audio, np.ndarray):
            return ""

        # Flatten / ensure 1D
        if audio.ndim > 1:
            audio = audio[:, 0]
        audio_flat = audio.astype(np.float32)

        # Skip if silence
        if len(audio_flat) == 0 or np.max(np.abs(audio_flat)) < 0.005:
            return ""

        # Direct in-memory transcription if 16kHz, otherwise save and transcribe
        try:
            if sample_rate == 16000:
                segments, _ = self.model.transcribe(
                    audio_flat,
                    language=language,
                    vad_filter=True,
                    beam_size=5,
                )
            else:
                sf.write(AUDIO_PATH, audio_flat, sample_rate)
                segments, _ = self.model.transcribe(
                    AUDIO_PATH,
                    language=language,
                    vad_filter=True,
                    beam_size=5,
                )

            return " ".join(seg.text for seg in segments).strip()

        except Exception as e:
            # Fallback to writing to disk
            try:
                sf.write(AUDIO_PATH, audio_flat, sample_rate)
                segments, _ = self.model.transcribe(
                    AUDIO_PATH,
                    language=language,
                    vad_filter=True,
                    beam_size=5,
                )
                return " ".join(seg.text for seg in segments).strip()
            except Exception as err:
                print(f"  [STT error] {err}")
                return ""

    def listen(
        self,
        seconds: float = RECORD_SECONDS,
    ) -> str:
        """Record from microphone and return transcribed text."""
        print(f"  Listening for {seconds}s...")

        audio = sd.rec(
            int(seconds * SAMPLE_RATE),
            device=config.MIC_DEVICE_INDEX,
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
        )

        sd.wait()
        return self.transcribe(audio, sample_rate=SAMPLE_RATE)
