import sounddevice as sd
import soundfile as sf
from faster_whisper import WhisperModel

SAMPLE_RATE = 16000
RECORD_SECONDS = 5
MIC_DEVICE = 1

print("Sohan is listening...")
audio = sd.rec(
    int(RECORD_SECONDS * SAMPLE_RATE),
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype="float32",
    device=MIC_DEVICE
)

sd.wait()
sf.write("speech.wav", audio, SAMPLE_RATE)

print("Processing your voice...")

model = WhisperModel("small", device="cpu", compute_type="int8")
segments, info = model.transcribe("speech.wav")
text = " ".join(segment.text for segment in segments).strip()

print("\nSohan heard:")
print(text)