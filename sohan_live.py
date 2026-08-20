import asyncio
import numpy as np
import sounddevice as sd
from google import genai

MODEL = "gemini-3.1-flash-live-preview"

client = genai.Client()

MIC_DEVICE = 1
MIC_RATE = 16000
SPEAKER_RATE = 24000
CHANNELS = 1


async def main():

    config = {
        "response_modalities": ["AUDIO"],
    }

    print("Connecting to Sohan...")

    async with client.aio.live.connect(
        model=MODEL,
        config=config,
    ) as session:

        print("Sohan connected.")
        print("Speak normally. Say 'Sohan, goodbye' to stop.\n")

        # Microphone callback
        mic_queue = asyncio.Queue()

        def microphone_callback(indata, frames, time, status):

            if status:
                print("MIC:", status)

            audio = (indata[:, 0] * 32767).astype(np.int16)
            mic_queue.put_nowait(audio.tobytes())

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

                async def send_microphone():

                    while True:

                        audio = await mic_queue.get()

                        await session.send_realtime_input(
                            audio={
                                "data": audio,
                                "mime_type": "audio/pcm;rate=16000",
                            }
                        )

                async def receive_response():

                    async for response in session.receive():

                        if not response.server_content:
                            continue

                        if response.server_content.model_turn:

                            for part in response.server_content.model_turn.parts:

                                if part.inline_data:

                                    audio_bytes = part.inline_data.data

                                    audio = np.frombuffer(
                                        audio_bytes,
                                        dtype=np.int16,
                                    )

                                    speaker.write(audio)

                        if response.server_content.turn_complete:
                            print("\nSohan finished.\n")

                await asyncio.gather(
                    send_microphone(),
                    receive_response(),
                )


if __name__ == "__main__":
    asyncio.run(main())