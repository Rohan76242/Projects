"""Z3RO wake-word detection module.

Loads the custom-trained wake-word CNN model and listens on the
microphone for the trigger word. When detected, calls the provided
callback function.
"""

import time
import queue

import numpy as np
import sounddevice as sd
import torch
import torchaudio

from torch import nn
from z3ro.config import config


# ============================================================
# SETTINGS
# ============================================================

SAMPLE_RATE = config.AUDIO_SAMPLE_RATE

# The model was trained on 1-second audio
WINDOW_SECONDS = 1.0

WINDOW_SAMPLES = int(
    SAMPLE_RATE * WINDOW_SECONDS
)

# Microphone chunk size
BLOCK_SIZE = 1600  # 0.1 second

# Wake-word confidence threshold (0.50 aligns with training/evaluation)
THRESHOLD = config.WAKEWORD_THRESHOLD

# Number of consecutive detections required
REQUIRED_DETECTIONS = 1

# Prevent immediate repeated triggers
COOLDOWN_SECONDS = 1.5


# ============================================================
# MODEL
# ============================================================

class WakeWordModel(nn.Module):

    def __init__(self):

        super().__init__()

        self.network = nn.Sequential(

            nn.Conv2d(
                1,
                16,
                kernel_size=3,
                padding=1
            ),

            nn.BatchNorm2d(16),

            nn.ReLU(),

            nn.MaxPool2d(2),

            nn.Conv2d(
                16,
                32,
                kernel_size=3,
                padding=1
            ),

            nn.BatchNorm2d(32),

            nn.ReLU(),

            nn.MaxPool2d(2),

            nn.Conv2d(
                32,
                64,
                kernel_size=3,
                padding=1
            ),

            nn.BatchNorm2d(64),

            nn.ReLU(),

            nn.AdaptiveAvgPool2d(
                (1, 1)
            ),

            nn.Flatten(),

            nn.Linear(
                64,
                32
            ),

            nn.ReLU(),

            nn.Dropout(0.3),

            nn.Linear(
                32,
                2
            )
        )

    def forward(self, x):

        return self.network(x)


# ============================================================
# MFCC
# ============================================================

mfcc_transform = torchaudio.transforms.MFCC(
    sample_rate=SAMPLE_RATE,

    n_mfcc=40,

    melkwargs={
        "n_fft": 400,
        "hop_length": 160,
        "n_mels": 64
    }
)


# ============================================================
# AUDIO -> MFCC
# ============================================================

def audio_to_features(audio):

    waveform = torch.from_numpy(
        audio.astype(np.float32)
    )

    # [samples] -> [1, samples]

    waveform = waveform.unsqueeze(0)

    # Exactly 1 second

    if waveform.shape[1] < WINDOW_SAMPLES:

        waveform = torch.nn.functional.pad(
            waveform,
            (
                0,
                WINDOW_SAMPLES - waveform.shape[1]
            )
        )

    else:

        waveform = waveform[
            :,
            :WINDOW_SAMPLES
        ]

    # MFCC

    features = mfcc_transform(
        waveform
    )

    # [1, 40, 101]
    # -> [1, 1, 40, 101]

    features = features.unsqueeze(0)

    return features


# ============================================================
# WAKE LISTENER
# ============================================================

class WakeListener:
    """Listen for the Z3RO wake word on the microphone."""

    def __init__(
        self,
        model_path: str,
    ):

        self.device = torch.device(
            "cuda"
            if torch.cuda.is_available()
            else "cpu"
        )

        self.model = WakeWordModel().to(
            self.device
        )

        checkpoint = torch.load(
            model_path,
            map_location=self.device,
        )

        self.model.load_state_dict(
            checkpoint
        )

        self.model.eval()

        self._audio_queue = queue.Queue()

    def _audio_callback(
        self,
        indata,
        frames,
        time_info,
        status,
    ):

        if status:
            print(
                f"  [mic] {status}"
            )

        audio = indata[:, 0].copy()

        self._audio_queue.put(
            audio
        )

    def wait_for_wake(self):
        """Block until the wake word is detected. Returns confidence."""

        audio_buffer = np.zeros(
            WINDOW_SAMPLES,
            dtype=np.float32,
        )

        consecutive = 0
        last_trigger = 0

        with sd.InputStream(
            device=config.MIC_DEVICE_INDEX,
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=BLOCK_SIZE,
            callback=self._audio_callback,
        ):

            while True:

                chunk = self._audio_queue.get()

                chunk_length = len(chunk)

                # Shift old audio left
                audio_buffer[:-chunk_length] = (
                    audio_buffer[chunk_length:]
                )

                # Add newest audio
                audio_buffer[-chunk_length:] = chunk

                # Calculate live audio level (RMS)
                rms = float(np.sqrt(np.mean(chunk**2)))
                level_pct = min(rms * 100, 100)
                vol_blocks = int(min(rms * 40, 5))
                vol_meter = "#" * vol_blocks + "-" * (5 - vol_blocks)

                # Create MFCC
                features = audio_to_features(
                    audio_buffer
                )

                features = features.to(
                    self.device
                )

                # Predict
                with torch.no_grad():

                    output = self.model(
                        features
                    )

                    probabilities = torch.softmax(
                        output,
                        dim=1,
                    )

                    confidence = (
                        probabilities[0][1].item()
                    )

                # Detection logic
                if confidence >= THRESHOLD:
                    consecutive += 1
                else:
                    consecutive = 0

                current_time = time.time()

                print(
                    f"\r  [mic: {vol_meter}] [wake score: {confidence:.3f}]",
                    end="",
                    flush=True,
                )

                if (
                    consecutive >= REQUIRED_DETECTIONS
                    and current_time - last_trigger >= COOLDOWN_SECONDS
                ):
                    print(f" -> TRIGGERED! ({confidence * 100:.0f}%)")
                    return confidence
