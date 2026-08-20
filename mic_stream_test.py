import sounddevice as sd

DEVICE = 1
RATE = 16000

def callback(indata, frames, time, status):
    if status:
        print("STATUS:", status)

    volume = abs(indata).mean()

    if volume > 0.01:
        print("🎙️ voice detected")

print("Listening continuously...")
print("Speak for 10 seconds.")
print("Press Ctrl+C to stop.")

with sd.InputStream(
    device=DEVICE,
    samplerate=RATE,
    channels=1,
    dtype="float32",
    blocksize=1600,
    callback=callback,
):
    sd.sleep(10000)

print("Done.")