import os
import sounddevice as sd
import soundfile as sf

BASE_DIR = r"C:\sobia\wakeword"
NEGATIVE_DIR = os.path.join(BASE_DIR, "negative")

SAMPLE_RATE = 16000
DURATION = 1.5
TARGET_SAMPLES = 200

os.makedirs(NEGATIVE_DIR, exist_ok=True)

existing = [
    f for f in os.listdir(NEGATIVE_DIR)
    if f.lower().endswith(".wav")
]

start_number = len(existing) + 1

print("===================================")
print("   NEGATIVE SAMPLE RECORDER")
print("===================================")
print()
print(f"Existing negative samples: {len(existing)}")
print(f"Target negative samples:   {TARGET_SAMPLES}")
print()

if len(existing) >= TARGET_SAMPLES:
    print("You already have 200 negative samples.")
    input("Press Enter to exit...")
    raise SystemExit

print("Instructions:")
print()
print("Say RANDOM words/sentences.")
print("DO NOT say the wake word 'Sobia'.")
print()
print("Examples:")
print("  hello")
print("  how are you")
print("  open the door")
print("  good morning")
print("  what time is it")
print("  testing microphone")
print("  random sentence")
print()
print("You can also make background noise.")
print()

input("Press ENTER when you are ready...")

for number in range(start_number, TARGET_SAMPLES + 1):

    filename = f"negative_{number:03d}.wav"
    filepath = os.path.join(NEGATIVE_DIR, filename)

    print()
    print(f"Recording {number}/{TARGET_SAMPLES}")
    print("Speak now...")

    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32"
    )

    sd.wait()

    sf.write(
        filepath,
        audio,
        SAMPLE_RATE
    )

    print(f"Saved: {filename}")

    if number < TARGET_SAMPLES:
        input("Press ENTER for next recording...")

print()
print("===================================")
print("DONE!")
print("===================================")
print(f"Negative samples: {TARGET_SAMPLES}")
print(f"Saved in: {NEGATIVE_DIR}")