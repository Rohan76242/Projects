import os
import time
import sounddevice as sd
import soundfile as sf

SAMPLE_RATE = 16000
DURATION = 1.2
TOTAL = 100

OUTPUT = "positive"

os.makedirs(OUTPUT, exist_ok=True)

print()
print("SOBIA WAKE-WORD RECORDER")
print("=========================")
print()
print("You will record yourself saying:")
print()
print("        SOBIA")
print()
print("Say it naturally each time.")
print("Change your distance and volume occasionally.")
print()
print("Starting in 3 seconds...")
time.sleep(3)

for i in range(1, TOTAL + 1):

    print(f"\nRecording {i}/{TOTAL}")

    for countdown in [3, 2, 1]:
        print(countdown)
        time.sleep(0.5)

    print("SAY: SOBIA")

    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
    )

    sd.wait()

    filename = os.path.join(
        OUTPUT,
        f"sobia_{i:03d}.wav"
    )

    sf.write(
        filename,
        audio,
        SAMPLE_RATE,
    )

    print("Saved:", filename)

print()
print("DONE!")
print(f"{TOTAL} recordings saved in ./{OUTPUT}/")