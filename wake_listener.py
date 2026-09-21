import os
import time

import numpy as np
import sounddevice as sd
import soundfile as sf
import torch
import torchaudio
from torch import nn


# ============================================================
# SETTINGS
# ============================================================

BASE_DIR = r"C:\sobia\wakeword"

MODEL_PATH = os.path.join(
    BASE_DIR,
    "wakeword_model.pth"
)

SAMPLE_RATE = 16000

# How much audio the model examines at once
WINDOW_SECONDS = 1.0

# Microphone chunk size
CHUNK_SECONDS = 0.25

WINDOW_SAMPLES = int(
    SAMPLE_RATE * WINDOW_SECONDS
)

CHUNK_SAMPLES = int(
    SAMPLE_RATE * CHUNK_SECONDS
)

# Model must be sufficiently confident
WAKE_THRESHOLD = 0.80

# Prevent triggering repeatedly
COOLDOWN_SECONDS = 2.0


# ============================================================
# MODEL
# IMPORTANT: This MUST match train.py
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
# MUST MATCH TRAINING
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
# AUDIO -> MODEL FEATURES
# ============================================================

def audio_to_features(audio):

    # Convert numpy -> torch
    waveform = torch.from_numpy(
        audio.astype(np.float32)
    )

    # Shape:
    # [samples]
    #
    # becomes:
    # [1, samples]

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
    #
    # Model expects:
    # [batch, channel, 40, 101]

    features = features.unsqueeze(0)

    return features


# ============================================================
# WAKE WORD DETECTION
# ============================================================

def predict(model, audio, device):

    features = audio_to_features(
        audio
    )

    features = features.to(device)

    with torch.no_grad():

        output = model(
            features
        )

        probabilities = torch.softmax(
            output,
            dim=1
        )

        wake_probability = (
            probabilities[0][1].item()
        )

    return wake_probability


# ============================================================
# WHEN WAKE WORD IS DETECTED
# ============================================================

def on_wake_word():

    print()
    print("================================")
    print("🔥 Z3RO WAKE WORD DETECTED!")
    print("================================")
    print()

    # --------------------------------------------------------
    # LATER:
    # We will connect this function to your Z3RO AI.
    #
    # For now it simply confirms detection.
    # --------------------------------------------------------

    print("Z3RO ACTIVATED.")
    print()


# ============================================================
# MAIN LISTENER
# ============================================================

def main():

    print("========================================")
    print("        Z3RO WAKE WORD LISTENER")
    print("========================================")
    print()

    # --------------------------------------------------------
    # Check model
    # --------------------------------------------------------

    if not os.path.exists(MODEL_PATH):

        print("ERROR: Model not found:")
        print(MODEL_PATH)

        return

    # --------------------------------------------------------
    # Device
    # --------------------------------------------------------

    device = torch.device(

        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print(
        f"Device: {device}"
    )

    # --------------------------------------------------------
    # Load model
    # --------------------------------------------------------

    print(
        "Loading wake-word model..."
    )

    model = WakeWordModel().to(
        device
    )

    checkpoint = torch.load(
        MODEL_PATH,
        map_location=device
    )

    model.load_state_dict(
        checkpoint
    )

    model.eval()

    print(
        "Model loaded successfully."
    )

    print()

    # --------------------------------------------------------
    # Microphone
    # --------------------------------------------------------

    print(
        "Starting microphone..."
    )

    print()

    print("----------------------------------------")
    print("Listening for: SOHAN")
    print(
        f"Threshold: {WAKE_THRESHOLD:.2f}"
    )
    print("----------------------------------------")
    print()

    print(
        "Speak the wake word..."
    )

    print(
        "Press CTRL+C to stop."
    )

    print()

    # --------------------------------------------------------
    # Audio buffer
    # --------------------------------------------------------

    audio_buffer = np.zeros(
        WINDOW_SAMPLES,
        dtype=np.float32
    )

    last_detection = 0.0

    # --------------------------------------------------------
    # Microphone callback
    # --------------------------------------------------------

    def audio_callback(
        indata,
        frames,
        callback_time,
        status
    ):

        nonlocal audio_buffer
        nonlocal last_detection

        if status:

            print(
                f"Audio status: {status}"
            )

        # Get mono microphone audio
        chunk = (
            indata[:, 0]
            .copy()
        )

        # Shift old audio left
        audio_buffer = np.roll(
            audio_buffer,
            -len(chunk)
        )

        # Add newest audio
        audio_buffer[
            -len(chunk):
        ] = chunk

        # Don't detect too frequently
        now = time.time()

        if (
            now - last_detection
            < COOLDOWN_SECONDS
        ):

            return

        try:

            wake_probability = predict(
                model,
                audio_buffer.copy(),
                device
            )

            print(
                f"\rWake probability: "
                f"{wake_probability:.3f}",
                end="",
                flush=True
            )

            # ------------------------------------------------
            # Detection
            # ------------------------------------------------

            if (
                wake_probability
                >= WAKE_THRESHOLD
            ):

                last_detection = now

                print()
                print()

                on_wake_word()

        except Exception as e:

            print()
            print(
                f"Prediction error: {e}"
            )

    # --------------------------------------------------------
    # Start microphone stream
    # --------------------------------------------------------

    try:

       with sd.InputStream(
    device=1,
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype="float32",
    blocksize=CHUNK_SAMPLES,
    callback=audio_callback
):
            while True:

                time.sleep(0.1)

    except KeyboardInterrupt:

        print()
        print()
        print(
            "Z3RO wake listener stopped."
        )

    except Exception as e:

        print()
        print(
            "MICROPHONE ERROR:"
        )

        print(e)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()