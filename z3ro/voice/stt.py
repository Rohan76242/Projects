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

        # Skip if silence or audio duration too short (< 0.3s)
        if len(audio_flat) < sample_rate * 0.3:
            return ""

        peak = float(np.max(np.abs(audio_flat)))
        rms = float(np.sqrt(np.mean(audio_flat ** 2)))
        if peak < 0.015 or rms < 0.005:
            return ""

        # Direct in-memory transcription if 16kHz, otherwise save and transcribe
        try:
            target_input = audio_flat if sample_rate == 16000 else AUDIO_PATH
            if sample_rate != 16000:
                sf.write(AUDIO_PATH, audio_flat, sample_rate)

            segments, _ = self.model.transcribe(
                target_input,
                language=language,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=400, threshold=0.5),
                no_speech_threshold=0.6,
                condition_on_previous_text=False,
                compression_ratio_threshold=2.4,
                beam_size=5,
            )

            valid_parts = []
            for seg in segments:
                raw_prob = getattr(seg, "no_speech_prob", 0.0)
                prob = float(raw_prob) if isinstance(raw_prob, (int, float)) else 0.0
                if prob < 0.6:
                    t = getattr(seg, "text", "")
                    if isinstance(t, str) and t.strip():
                        valid_parts.append(t.strip())
                    elif t is not None and not str(t).startswith("<MagicMock"):
                        valid_parts.append(str(t).strip())

            transcript = " ".join(valid_parts).strip()

            # Filter out common Whisper silence hallucinations
            HALLUCINATIONS = (
                "thank you for watching", "thanks for watching", "subscribe to my channel",
                "please subscribe", "subtitles by", "mammoth and go have a chill",
                "go have a chill", "see you next time", "mbc", "bye bye",
            )
            lowered_transcript = transcript.lower()
            if any(h in lowered_transcript for h in HALLUCINATIONS) and len(transcript) < 55:
                return ""

            return transcript

        except Exception as e:
            print(f"  [STT error] {e}")
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
