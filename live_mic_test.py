import asyncio
import sounddevice as sd

from google import genai
from google.genai import types


MODEL = "gemini-3.1-flash-live-preview"

MIC_DEVICE = 1
MIC_RATE = 16000
SPEAKER_RATE = 24000
BLOCK_SIZE = 1024

client = genai.Client()


async def main():

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
    )

    async with client.aio.live.connect(
        model=MODEL,
        config=config,
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

        # -------------------------
        # MICROPHONE START
        # -------------------------

        with sd.InputStream(
            device=MIC_DEVICE,
            samplerate=MIC_RATE,
            channels=1,
            dtype="int16",
            blocksize=BLOCK_SIZE,
            latency="low",
            callback=mic_callback,
        ):

            # -------------------------
            # RECEIVE GEMINI AUDIO
            # -------------------------

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


if __name__ == "__main__":
    asyncio.run(main())