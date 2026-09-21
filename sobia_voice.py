import asyncio
import sounddevice as sd

from google.genai import types
from sobia_core import SOBIA, MODEL


MIC_DEVICE = 1
MIC_RATE = 16000
SPEAKER_RATE = 24000
BLOCK_SIZE = 1024


async def main():

    sobia = SOBIA()

    print("================================")
    print("       SOBIA VOICE ONLINE")
    print("================================")

    async with sobia.client.aio.live.connect(
        model=MODEL,
        config=sobia.get_live_config(),
    ) as session:

        print("CONNECTED")

        loop = asyncio.get_running_loop()

        # -------------------------
        # MICROPHONE
        # -------------------------

        def mic_callback(indata, frames, time_info, status):

            if status:
                print("MIC:", status, flush=True)

            audio = indata[:, 0].copy().tobytes()

            asyncio.run_coroutine_threadsafe(
                session.send_realtime_input(
                    audio=types.Blob(
                        data=audio,
                        mime_type="audio/pcm;rate=16000",
                    )
                ),
                loop,
            )

        # -------------------------
        # SPEAKER
        # -------------------------

        speaker = sd.RawOutputStream(
            samplerate=SPEAKER_RATE,
            channels=1,
            dtype="int16",
            blocksize=1024,
        )

        speaker.start()

        print("MIC READY")
        print("SPEAKER READY")
        print("SPEAK NOW\n")

        try:

            with sd.InputStream(
                device=MIC_DEVICE,
                samplerate=MIC_RATE,
                channels=1,
                dtype="int16",
                blocksize=BLOCK_SIZE,
                latency="low",
                callback=mic_callback,
            ):

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

                    if content.turn_complete:

                        print("READY", flush=True)

        finally:

            speaker.stop()
            speaker.close()


if __name__ == "__main__":
    asyncio.run(main())