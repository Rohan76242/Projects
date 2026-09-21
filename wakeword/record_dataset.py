import os
import time
import numpy as np
import sounddevice as sd
import soundfile as sf

# ============================================================
# SOBIA WAKE-WORD DATASET RECORDER
# ============================================================

BASE_DIR = r"C:\sobia\wakeword"

POSITIVE_DIR = os.path.join(BASE_DIR, "positive")
NEGATIVE_DIR = os.path.join(BASE_DIR, "negative")

SAMPLE_RATE = 16000
CHANNELS = 1
DEVICE = 1

RECORD_SECONDS = 1.2

# Number of NEW recordings to make
POSITIVE_COUNT = 50
NEGATIVE_COUNT = 50


# ============================================================
# SETUP
# ============================================================

os.makedirs(POSITIVE_DIR, exist_ok=True)
os.makedirs(NEGATIVE_DIR, exist_ok=True)


def record_audio():
    print()
    print("Recording...")

    audio = sd.rec(
        int(RECORD_SECONDS * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="float32",
        device=DEVICE
    )

    sd.wait()

    return audio


def next_filename(folder, prefix):
    existing = []

    for name in os.listdir(folder):
        if name.lower().endswith(".wav"):
            existing.append(name)

    number = len(existing) + 1

    while True:
        filename = f"{prefix}_{number:03d}.wav"
        path = os.path.join(folder, filename)

        if not os.path.exists(path):
            return path

        number += 1


# ============================================================
# POSITIVE RECORDINGS
# ============================================================

def record_positive():

    print()
    print("==========================================")
    print("       SOBIA POSITIVE RECORDINGS")
    print("==========================================")
    print()
    print(f"Recording {POSITIVE_COUNT} new samples.")
    print()
    print('Say: "SOBIA"')
    print()
    print("Each recording is 1.2 seconds.")
    print("Speak naturally.")
    print()

    input("Press ENTER to start...")

    for i in range(POSITIVE_COUNT):

        print()
        print("------------------------------------------")
        print(f"Positive sample {i + 1}/{POSITIVE_COUNT}")
        print("------------------------------------------")

        print("Get ready...")
        time.sleep(1)

        print('SAY "SOBIA" NOW!')

        audio = record_audio()

        path = next_filename(
            POSITIVE_DIR,
            "sobia"
        )

        sf.write(
            path,
            audio,
            SAMPLE_RATE
        )

        print(f"Saved: {path}")

        time.sleep(0.5)

    print()
    print("==========================================")
    print("Positive recordings complete!")
    print("==========================================")


# ============================================================
# NEGATIVE RECORDINGS
# ============================================================

def record_negative():

    print()
    print("==========================================")
    print("       SOBIA NEGATIVE RECORDINGS")
    print("==========================================")
    print()
    print(f"Recording {NEGATIVE_COUNT} new samples.")
    print()
    print("DO NOT say SOBIA.")
    print()
    print("Say normal sentences such as:")
    print()
    print("Hello how are you")
    print("Open my browser")
    print("What is the weather")
    print("Tell me the time")
    print("Play some music")
    print("I need help with this")
    print()
    print("You can also record silence/background noise.")
    print()

    input("Press ENTER to start...")

    for i in range(NEGATIVE_COUNT):

        print()
        print("------------------------------------------")
        print(f"Negative sample {i + 1}/{NEGATIVE_COUNT}")
        print("------------------------------------------")

        print("Get ready...")
        time.sleep(1)

        print("SPEAK NORMAL WORDS — NOT SOBIA!")

        audio = record_audio()

        path = next_filename(
            NEGATIVE_DIR,
            "negative"
        )

        sf.write(
            path,
            audio,
            SAMPLE_RATE
        )

        print(f"Saved: {path}")

        time.sleep(0.5)

    print()
    print("==========================================")
    print("Negative recordings complete!")
    print("==========================================")


# ============================================================
# MAIN
# ============================================================

def main():

    print()
    print("==========================================")
    print("       SOBIA DATASET RECORDER")
    print("==========================================")
    print()

    print(f"Microphone device: {DEVICE}")
    print(f"Sample rate: {SAMPLE_RATE}")
    print(f"Recording length: {RECORD_SECONDS} seconds")
    print()

    print("Choose what to record:")
    print()
    print("1 = Positive samples (say SOBIA)")
    print("2 = Negative samples (normal speech)")
    print("3 = Both")
    print()

    choice = input("Enter choice: ").strip()

    if choice == "1":
        record_positive()

    elif choice == "2":
        record_negative()

    elif choice == "3":
        record_positive()
        record_negative()

    else:
        print("Invalid choice.")

    print()
    print("Dataset recorder finished.")


if __name__ == "__main__":
    main()