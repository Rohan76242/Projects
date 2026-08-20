import asyncio
import time

from google import genai
from google.genai import types


MODEL = "gemini-3.1-flash-live-preview"

client = genai.Client()


async def main():

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
    )

    async with client.aio.live.connect(
        model=MODEL,
        config=config,
    ) as session:

        print("Connected.")

        start = time.perf_counter()

        await session.send_realtime_input(
            text="Say hello to me in one short sentence."
        )

        first_audio = None

        async for response in session.receive():

            if not response.server_content:
                continue

            content = response.server_content

            if content.model_turn:

                for part in content.model_turn.parts:

                    if part.inline_data:

                        if first_audio is None:
                            first_audio = (
                                time.perf_counter()
                                - start
                            )

                            print(
                                f"First audio: "
                                f"{first_audio:.2f} seconds"
                            )

            if content.turn_complete:
                break


if __name__ == "__main__":
    asyncio.run(main())