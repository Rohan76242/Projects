import os
import time
import random

import numpy as np
import sounddevice as sd
import soundfile as sf

# ============================================================
# SETTINGS
# ============================================================

BASE_DIR = r"C:\sobia\wakeword"
NEGATIVE_DIR = os.path.join(BASE_DIR, "negative")

SAMPLE_RATE = 16000
RECORD_SECONDS = 1.2

TOTAL_NEW_NEGATIVES = 350

# Microphone device
MIC_DEVICE = 1

# ============================================================
# NEGATIVE PROMPTS
# ============================================================

PROMPTS = [
    "hello",
    "hey",
    "hey there",
    "hello there",
    "how are you",
    "what are you doing",
    "open browser",
    "open chrome",
    "open youtube",
    "open calculator",
    "start music",
    "play music",
    "stop music",
    "what time is it",
    "tell me the time",
    "what is the weather",
    "search this",
    "search google",
    "open my computer",
    "open settings",
    "turn on wifi",
    "turn off wifi",
    "good morning",
    "good night",
    "thank you",
    "okay",
    "yes",
    "no",
    "come here",
    "listen",
    "computer",
    "assistant",
    "google",
    "alexa",
    "hey assistant",
]

# ============================================================
# FIND NEXT FILE NUMBER
# ============================================================

def get_next_number():

    os.makedirs(
        NEGATIVE_DIR,
        exist_ok=True
    )

    numbers = []

    for filename in os.listdir(NEGATIVE_DIR):

        if not filename.lower().endswith(".wav"):
            continue

        name = os.path.splitext(filename)[0]

        try:
            number = int(
                name.split("_")[-1]
            )

            numbers.append(number)

        except ValueError:
            pass

    if not numbers:
        return 1

    return max(numbers) + 1


# ============================================================
# RECORD
# ============================================================

def record_audio():

    print()
    print("Recording...")

    audio = sd.rec(
        int(
            SAMPLE_RATE
            * RECORD_SECONDS
        ),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        device=MIC_DEVICE
    )

    sd.wait()

    return audio


# ============================================================
# MAIN
# ============================================================

def main():

    os.makedirs(
        NEGATIVE_DIR,
        exist_ok=True
    )

    start_number = get_next_number()

    print()
    print("========================================")
    print("       Z3RO NEGATIVE DATASET")
    print("========================================")
    print()

    print(
        f"Existing negatives: "
        f"{start_number - 1}"
    )

    print(
        f"New samples: "
        f"{TOTAL_NEW_NEGATIVES}"
    )

    print(
        f"Microphone: "
        f"{MIC_DEVICE}"
    )

    print()

    print(
        "IMPORTANT:"
    )

    print(
        "Do NOT say the wake word."
    )

    print(
        "Say the displayed sentence naturally."
    )

    print()

    input(
        "Press ENTER to start..."
    )

    for i in range(
        TOTAL_NEW_NEGATIVES
    ):

        number = (
            start_number + i
        )

        prompt = random.choice(
            PROMPTS
        )

        print()
        print("----------------------------------------")

        print(
            f"Sample "
            f"{i + 1}/{TOTAL_NEW_NEGATIVES}"
        )

        print(
            f'Say: "{prompt}"'
        )

        print(
            "Recording in 1 second..."
        )

        time.sleep(1)

        audio = record_audio()

        filename = os.path.join(
            NEGATIVE_DIR,
            f"negative_{number:03d}.wav"
        )

        sf.write(
            filename,
            audio,
            SAMPLE_RATE
        )

        print(
            f"Saved: {filename}"
        )

        # Small pause
        time.sleep(0.3)

    print()
    print("========================================")
    print("       RECORDING COMPLETE")
    print("========================================")
    print()

    print(
        f"Added {TOTAL_NEW_NEGATIVES} "
        "negative samples."
    )

    print(
        f"Negative dataset is now approximately "
        f"{start_number - 1 + TOTAL_NEW_NEGATIVES} samples."
    )


if __name__ == "__main__":
    main()