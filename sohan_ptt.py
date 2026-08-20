import asyncio
import time
import numpy as np
import sounddevice as sd
from pynput import keyboard

from google import genai
from google.genai import types


MODEL = "gemini-3.1-flash-live-preview"

MIC_DEVICE = 1
MIC_RATE = 16000
SPEAKER_RATE = 24000

BLOCK_SIZE = 320

client = genai.Client()

recording = False
audio_queue = asyncio.Queue()


def on_press(key):
    global recording

    if key == keyboard.Key.space:
        recording = True


def on_release(key):
    global recording

    if key == keyboard.Key.space:
        recording = False


async def main():

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
    )

    async with client.aio.live.connect(
        model=MODEL,
        config=config,
    ) as session:

        print("✅ Sohan connected.")
        print("Hold SPACE and speak.")
        print("Release SPACE when finished.\n")

        def mic_callback(
            indata,
            frames,
            time_info,
            status,
        ):

            if recording:

                audio = (
                    indata[:, 0] * 32767
                ).astype(np.int16)

                audio_queue.put_nowait(
                    audio.tobytes()
                )

        listener = keyboard.Listener(
            on_press=on_press,
            on_release=on_release,
        )

        listener.start()

        with sd.InputStream(
            device=MIC_DEVICE,
            samplerate=MIC_RATE,
            channels=1,
            dtype="float32",
            blocksize=BLOCK_SIZE,
            callback=mic_callback,
        ):

            with sd.RawOutputStream(
                samplerate=SPEAKER_RATE,
                channels=1,
                dtype="int16",
            ) as speaker:

                while True:

                    await asyncio.sleep(0.01)

                    if not recording:

                        if audio_queue.empty():
                            continue

                        print("Sending...")

                        while not audio_queue.empty():

                            audio = (
                                await audio_queue.get()
                            )

                            await session.send_realtime_input(
                                audio=types.Blob(
                                    data=audio,
                                    mime_type="audio/pcm;rate=16000",
                                )
                            )

                        await session.send_realtime_input(
                            audio_stream_end=True
                        )

                        start = time.perf_counter()

                        async for response in session.receive():

                            if not response.server_content:
                                continue

                            content = response.server_content

                            if content.model_turn:

                                for part in content.model_turn.parts:

                                    if part.inline_data:

                                        speaker.write(
                                            part.inline_data.data
                                        )

                                        elapsed = (
                                            time.perf_counter()
                                            - start
                                        )

                                        print(
                                            f"\rFirst audio: "
                                            f"{elapsed:.2f}s",
                                            end=""
                                        )

                            if content.turn_complete:
                                print("\n\nReady.")

                                break


if __name__ == "__main__":
    asyncio.run(main())