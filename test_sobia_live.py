import asyncio
import sounddevice as sd

from sobia_core import SOBIA, MODEL


SPEAKER_RATE = 24000


async def main():

    sobia = SOBIA()

    print("Connecting to SOBIA...")

    async with sobia.client.aio.live.connect(
        model=MODEL,
        config=sobia.get_live_config(),
    ) as session:

        print("SOBIA connected!")
        print("Sending test message...")

        await session.send_realtime_input(
            text="Introduce yourself in one short sentence."
        )

        print("SOBIA is responding...\n")

        with sd.RawOutputStream(
            samplerate=SPEAKER_RATE,
            channels=1,
            dtype="int16",
        ) as speaker:

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
                    break

    print("\nSOBIA finished.")


if __name__ == "__main__":
    asyncio.run(main())