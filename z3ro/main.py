"""Z3RO — Main entry point.

Runs the complete voice-controlled assistant loop:

    Wake word → Record command → Transcribe → Brain → Tools → Verify → Speak

Usage:
    python -m z3ro.main            (voice mode, default)
    python -m z3ro.main --type     (keyboard mode, skip wake word + STT)
"""

import os
import sys
import time
import argparse
from pathlib import Path

# Auto-Environment Bootstrap (Ensures dependencies like numpy/torch are loaded)
def _bootstrap_environment():
    try:
        import numpy
    except ModuleNotFoundError:
        candidate_venvs = [
            Path(r"C:\sobia\.venv\Scripts\python.exe"),
            Path(__file__).resolve().parent.parent / ".venv" / "Scripts" / "python.exe",
        ]
        current_exe = Path(sys.executable).resolve()
        for venv_py in candidate_venvs:
            if venv_py.is_file() and venv_py.resolve() != current_exe:
                import subprocess
                try:
                    res = subprocess.call([str(venv_py)] + sys.argv)
                    sys.exit(res)
                except Exception:
                    pass

_bootstrap_environment()

from z3ro.config import config


def run_voice_mode():
    """Full voice loop: wake → listen → act → speak."""

    # ------------------------------------------------
    # Find the wake-word model
    # ------------------------------------------------

    model_paths = [
        config.WAKEWORD_MODEL_PATH,
        os.path.join(
            os.path.dirname(__file__),
            "..",
            "wakeword_model.pth",
        ),
        r"C:\sobia\wakeword\wakeword_model.pth",
    ]

    wake_model = None

    for path in model_paths:
        if os.path.isfile(path):
            wake_model = os.path.abspath(path)
            break

    if wake_model is None:

        print(
            "ERROR: Could not find "
            "wakeword_model.pth"
        )

        print(
            "Falling back to keyboard mode."
        )

        run_type_mode()
        return

    # ------------------------------------------------
    # Load all components
    # ------------------------------------------------

    print()
    print("========================================")
    print("             Z3RO LOADING")
    print("========================================")
    print()

    t0 = time.perf_counter()

    print("[1/4] Loading brain...")
    from z3ro.agent import Z3ROAgent
    agent = Z3ROAgent()
    print("  Brain ready.")

    print("[2/4] Loading wake-word detector...")
    from z3ro.voice.wake import WakeListener
    wake = WakeListener(wake_model)
    print("  Wake-word ready.")

    print("[3/4] Loading speech-to-text...")
    from z3ro.voice.stt import STT
    stt = STT()

    print("[4/4] Loading text-to-speech...")
    from z3ro.voice.tts import TTS
    tts = TTS()

    load_time = time.perf_counter() - t0

    print()
    print("========================================")
    print("             Z3RO READY")
    print("========================================")
    print()
    print(f"  Brain:  Qwen 2.5 1.5B Instruct")
    print(f"  Vision: Moondream")
    print(f"  STT:    Whisper (small, int8)")
    print(f"  TTS:    pyttsx3 (offline)")
    print(f"  Wake:   Custom CNN")
    print(f"  Loaded in {load_time:.1f}s")
    print()
    print("  Say 'Z3RO' to activate.")
    print("  Press CTRL+C to quit.")
    print()

    # ------------------------------------------------
    # Main loop
    # ------------------------------------------------

    try:

        while True:

            # Step 1: Wait for wake word
            print(
                "💤 Waiting for wake word..."
            )

            confidence = wake.wait_for_wake()

            print()
            print(
                "========================================")
            print(
                "  🔥 Z3RO ACTIVATED  "
                f"({confidence * 100:.0f}%)"
            )
            print(
                "========================================")
            print()

            # Step 2: Record and transcribe command
            tts.say("Yes?")

            command = stt.listen(
                seconds=4,
            )

            if not command:

                print(
                    "  No speech detected."
                )

                tts.say(
                    "I didn't hear anything."
                )

                print()
                continue

            print(
                f"  You said: {command}"
            )

            # Step 3: Execute through Z3RO agent
            t_start = time.perf_counter()

            results = agent.handle(
                command
            )

            elapsed = (
                time.perf_counter() - t_start
            )

            # Step 4: Report results
            print()

            for result in results:

                print(
                    f"  Z3RO: {result}"
                )

            print(
                f"  [timing] Total: "
                f"{elapsed:.2f}s"
            )

            # Step 5: Speak summary
            if results:

                last = results[-1]

                # Keep spoken response short
                if len(last) > 80:
                    last = last[:80]

                tts.say(f"Done. {last}")

            else:

                tts.say("Done.")

            print()

    except KeyboardInterrupt:

        print()
        print("Z3RO: Shutting down.")


def run_type_mode():
    """Keyboard mode: type commands, skip voice."""

    from z3ro.agent import Z3ROAgent

    print()
    print("========================================")
    print("          Z3RO AGENT (keyboard)")
    print("========================================")
    print()
    print("  Brain: Qwen 2.5 1.5B Instruct")
    print("  Vision: Moondream")
    print("  Type 'exit' to quit.")
    print()

    agent = Z3ROAgent()

    while True:

        user_input = input(
            "You: "
        ).strip()

        if user_input.lower() == "exit":

            print(
                "Z3RO: Shutting down."
            )

            break

        if not user_input:
            continue

        results = agent.handle(
            user_input
        )

        print()

        for result in results:

            print(
                f"Z3RO: {result}"
            )

        print()


# ============================================================
# Entry point
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Z3RO Computer Control Agent",
    )

    parser.add_argument(
        "--type",
        action="store_true",
        help="Keyboard mode (skip voice)",
        dest="type_mode",
    )

    args = parser.parse_args()

    if args.type_mode:
        run_type_mode()
    else:
        run_voice_mode()


if __name__ == "__main__":
    main()
