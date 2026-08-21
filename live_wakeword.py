import os
import time
import queue

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

# The model was trained on 1-second audio
WINDOW_SECONDS = 1.0

WINDOW_SAMPLES = int(
    SAMPLE_RATE * WINDOW_SECONDS
)

# Microphone chunk size
BLOCK_SIZE = 1600       # 0.1 second

# Wake-word confidence threshold
THRESHOLD = 0.80

# Number of consecutive detections required
REQUIRED_DETECTIONS = 2

# Prevent immediate repeated triggers
COOLDOWN_SECONDS = 2.0


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
# LOAD MODEL
# ============================================================

def load_model():

    print()
    print("Loading Z3RO wake-word model...")

    device = torch.device(
        "cuda"
        if torch.cuda.is_available()
        else "cpu"
    )

    print(
        f"Device: {device}"
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

    return model, device


# ============================================================
# MICROPHONE
# ============================================================

audio_queue = queue.Queue()


def audio_callback(
    indata,
    frames,
    time_info,
    status
):

    if status:

        print(
            f"Microphone: {status}"
        )

    audio = indata[:, 0].copy()

    audio_queue.put(
        audio
    )


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("======================================")
    print("       Z3RO LIVE WAKE WORD")
    print("======================================")

    print()
    print(
        "Wake threshold:",
        THRESHOLD
    )

    print(
        "Required detections:",
        REQUIRED_DETECTIONS
    )

    print()
    print(
        "Loading model..."
    )

    model, device = load_model()

    audio_buffer = np.zeros(
        WINDOW_SAMPLES,
        dtype=np.float32
    )

    consecutive_detections = 0

    last_trigger_time = 0

    print()
    print("--------------------------------------")
    print("Microphone starting...")
    print("--------------------------------------")

    print()
    print("Listening for: Z3RO")
    print("Press CTRL+C to stop.")
    print()

    try:

        with sd.InputStream(

            samplerate=SAMPLE_RATE,

            channels=1,

            dtype="float32",

            blocksize=BLOCK_SIZE,

            callback=audio_callback

        ):

            while True:

                chunk = audio_queue.get()

                chunk_length = len(chunk)

                # Shift old audio left

                audio_buffer[:-chunk_length] = (
                    audio_buffer[chunk_length:]
                )

                # Add newest audio

                audio_buffer[-chunk_length:] = chunk

                # Create MFCC

                features = audio_to_features(
                    audio_buffer
                )

                features = features.to(
                    device
                )

                # Predict

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

                # ------------------------------------------------
                # DETECTION
                # ------------------------------------------------

                if wake_probability >= THRESHOLD:

                    consecutive_detections += 1

                else:

                    consecutive_detections = 0

                # Display probability

                print(
                    f"\rWake probability: "
                    f"{wake_probability:.3f}   "
                    f"Detections: "
                    f"{consecutive_detections}/"
                    f"{REQUIRED_DETECTIONS}",
                    end=""
                )

                # ------------------------------------------------
                # WAKE WORD DETECTED
                # ------------------------------------------------

                current_time = time.time()

                if (

                    consecutive_detections
                    >= REQUIRED_DETECTIONS

                    and
                    current_time
                    -
                    last_trigger_time
                    >= COOLDOWN_SECONDS

                ):

                    print()
                    print()
                    print(
                        "======================================"
                    )

                    print(
                        "       Z3RO WAKE WORD DETECTED!"
                    )

                    print(
                        f"Confidence: "
                        f"{wake_probability * 100:.1f}%"
                    )

                    print(
                        "======================================"
                    )

                    # ------------------------------------------------
                    # THIS IS WHERE Z3RO SHOULD START
                    # ------------------------------------------------

                    print(
                        "Z3RO activated."
                    )

                    # TODO:
                    # Put your Z3RO assistant start function here.
                    #
                    # Example:
                    #
                    # start_z3ro()
                    #
                    # We are NOT starting the full assistant yet.
                    # First we verify wake-word detection.

                    last_trigger_time = (
                        current_time
                    )

                    consecutive_detections = 0

                    print()
                    print(
                        "Listening again..."
                    )

    except KeyboardInterrupt:

        print()
        print()
        print(
            "Stopping Z3RO wake-word listener..."
        )

    except Exception as e:

        print()
        print()
        print(
            "ERROR:"
        )

        print(e)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    main()