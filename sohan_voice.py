import asyncio
import numpy as np
import sounddevice as sd
import soundfile as sf

from faster_whisper import WhisperModel
from google import genai


MODEL = "gemini-3.1-flash-live-preview"

MIC_DEVICE = 1
MIC_RATE = 16000
SPEAKER_RATE = 24000


# -----------------------------
# Wake word
# -----------------------------

print("Loading wake-word engine...")

whisper = WhisperModel(
    "small",
    device="cpu",
    compute_type="int8",
)

print("Wake-word engine ready.")


def listen_for_wake_word():

    print("\n💤 Sohan is sleeping.")
    print("Say: Hey Sohan")

    while True:

        audio = sd.rec(
            int(3 * MIC_RATE),
            samplerate=MIC_RATE,
            channels=1,
            dtype="float32",
            device=MIC_DEVICE,
        )

        sd.wait()

        sf.write(
            "wake.wav",
            audio,
            MIC_RATE,
        )

        segments, _ = whisper.transcribe(
            "wake.wav",
            language="en",
            vad_filter=True,
            beam_size=5,
        )

        text = " ".join(
            segment.text
            for segment in segments
        ).lower()

        print("Heard:", text)

        if "hey sohan" in text:

            print("\n🔥 Sohan activated!\n")
            return


# -----------------------------
# Gemini Live
# -----------------------------

async def talk_to_sohan():

    client = genai.Client()

    config = {
        "response_modalities": ["AUDIO"],
    }

    async with client.aio.live.connect(
        model=MODEL,
        config=config,
    ) as session:

        mic_queue = asyncio.Queue()

        def microphone_callback(
            indata,
            frames,
            time,
            status,
        ):

            if status:
                print("MIC:", status)

            audio = (
                indata[:, 0] * 32767
            ).astype(np.int16)

            mic_queue.put_nowait(
                audio.tobytes()
            )

        with sd.InputStream(
            device=MIC_DEVICE,
            samplerate=MIC_RATE,
            channels=1,
            dtype="float32",
            blocksize=1600,
            callback=microphone_callback,
        ):

            with sd.OutputStream(
                samplerate=SPEAKER_RATE,
                channels=1,
                dtype="int16",
            ) as speaker:

                async def send_audio():

                    while True:

                        audio = await mic_queue.get()

                        await session.send_realtime_input(
                            audio={
                                "data": audio,
                                "mime_type":
                                "audio/pcm;rate=16000",
                            }
                        )

                async def receive_audio():

                    async for response in session.receive():

                        if not response.server_content:
                            continue

                        if response.server_content.model_turn:

                            for part in (
                                response
                                .server_content
                                .model_turn
                                .parts
                            ):

                                if part.inline_data:

                                    audio = np.frombuffer(
                                        part.inline_data.data,
                                        dtype=np.int16,
                                    )

                                    speaker.write(audio)

                        if response.server_content.turn_complete:

                            print(
                                "\nSohan finished.\n"
                            )

                await asyncio.gather(
                    send_audio(),
                    receive_audio(),
                )


# -----------------------------
# Main loop
# -----------------------------

async def main():

    while True:

        listen_for_wake_word()

        await talk_to_sohan()


if __name__ == "__main__":

    asyncio.run(main())