import sounddevice as sd
import numpy as np
import openwakeword
from openwakeword.model import Model


SAMPLE_RATE = 16000
BLOCK_SIZE = 1280

openwakeword.utils.download_models()

model = Model(
    wakeword_models=["hey_jarvis"]
)

print("Wake-word system ready.")
print("Say: Hey Jarvis")


def callback(indata, frames, time_info, status):

    if status:
        print(status)

    audio = indata[:, 0].copy()

    audio = (audio * 32767).astype(np.int16)

    prediction = model.predict(audio)

    for name, score in prediction.items():

        if score > 0.5:
            print(
                f"\nWAKE WORD DETECTED: {name} "
                f"({score:.2f})"
            )


with sd.InputStream(
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype="float32",
    blocksize=BLOCK_SIZE,
    callback=callback,
):

    print("Listening...\n")

    while True:
        sd.sleep(1000)