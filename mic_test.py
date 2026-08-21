import os
import wave
import numpy as np
import sounddevice as sd

# ============================================================
# Z3RO / SOBIA MICROPHONE RECORDER
# ============================================================

SAMPLE_RATE = 16000
CHANNELS = 1
RECORD_SECONDS = 1
OUTPUT_FILE = r"C:\sobia\wakeword\mic_test.wav"

print()
print("=" * 45)
print("        SOBIA WAKE WORD RECORDER")
print("=" * 45)
print()

print(f"Sample rate : {SAMPLE_RATE}")
print(f"Channels    : {CHANNELS}")
print(f"Duration    : {RECORD_SECONDS} second")
print()

input("Press ENTER, then say: SOBIA")

print()
print("Recording...")
print(">>> SAY: SOBIA <<<")

audio = sd.rec(
    int(RECORD_SECONDS * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=CHANNELS,
    dtype="int16"
)

sd.wait()

print("Recording finished.")

# Flatten mono audio
audio = audio.reshape(-1)

# Show recording information
audio_float = audio.astype(np.float32) / 32768.0

max_amplitude = np.max(np.abs(audio_float))
rms = np.sqrt(np.mean(audio_float ** 2))

print()
print("Recording information:")
print(f"Samples : {len(audio)}")
print(f"Max     : {max_amplitude:.4f}")
print(f"RMS     : {rms:.4f}")

# Save standard PCM WAV
with wave.open(OUTPUT_FILE, "wb") as wav:
    wav.setnchannels(CHANNELS)
    wav.setsampwidth(2)       # int16 = 2 bytes
    wav.setframerate(SAMPLE_RATE)
    wav.writeframes(audio.tobytes())

print()
print("Saved to:")
print(OUTPUT_FILE)
print()
print("=" * 45)