"""
=============================================================================
                    Z3RO / SOBIA UNIFIED RUNTIME (NAME.PY)
=============================================================================

Master entry point connecting all subsystems:
- Local Brain & Tool Execution (Qwen 2.5 1.5B)
- Screen Vision & Verification (Moondream)
- Voice Pipeline (CNN Wake-Word -> faster-whisper STT -> pyttsx3 TTS)
- SOBIA Cloud & Multimodal Engine (Gemini Live preview)
- Push-To-Talk (PTT) and Keyboard CLI Modes
- Self-Diagnostics & System Doctor

Usage:
    python name.py                         # Run default mode (voice)
    python name.py --name SOBIA            # Launch with SOBIA identity
    python name.py --mode type             # Interactive keyboard REPL
    python name.py --mode ptt              # Push-to-talk voice mode
    python name.py --task "open notepad"   # Autonomous one-shot execution
    python name.py --doctor                # Run pre-flight health checks
=============================================================================
"""

import sys
import os
import time
import signal
import argparse
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Ensure safe console output encoding on Windows
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from z3ro.config import config
from z3ro.logger import Colors, logger
from z3ro.doctor import SystemDoctor


def print_banner(assistant_name: str, mode: str, engine: str):
    """Display modern startup banner."""
    print(f"{Colors.BOLD}{Colors.CYAN}")
    print("  ███████╗██████╗ ██████╗  ██████╗ ")
    print("  ╚══███╔╝╚════██╗██╔══██╗██╔═══██╗")
    print("    ███╔╝  █████╔╝██████╔╝██║   ██║")
    print("   ███╔╝   ╚═══██╗██╔══██╗██║   ██║")
    print("  ███████╗██████╔╝██║  ██║╚██████╔╝")
    print("  ╚══════╝╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ")
    print(f"{Colors.RESET}")
    print(f"  {Colors.BOLD}{Colors.WHITE}Unified Assistant Platform{Colors.RESET} {Colors.DIM}[Production Build v1.0]{Colors.RESET}")
    print(f"  {Colors.CYAN}--------------------------------------------------{Colors.RESET}")
    print(f"  {Colors.BOLD}Identity:{Colors.RESET}   {Colors.GREEN}{assistant_name}{Colors.RESET}")
    print(f"  {Colors.BOLD}Engine:{Colors.RESET}     {Colors.YELLOW}{engine.upper()}{Colors.RESET} (Brain: {config.BRAIN_MODEL} | Vision: {config.VISION_MODEL})")
    print(f"  {Colors.BOLD}Active Mode:{Colors.RESET} {Colors.MAGENTA}{mode.upper()}{Colors.RESET}")
    print(f"  {Colors.CYAN}--------------------------------------------------{Colors.RESET}\n")


def run_one_shot_task(task_instruction: str, agent=None):
    """Execute a single autonomous instruction from start to finish."""
    if agent is None:
        from z3ro.agent import Z3ROAgent
        agent = Z3ROAgent()

    logger.info(f"Executing task: '{task_instruction}'")
    results = agent.run(task_instruction)
    print()
    print(f"{Colors.BOLD}{Colors.GREEN}Task Execution Summary:{Colors.RESET}")
    for idx, r in enumerate(results, 1):
        print(f"  [{idx}] {r}")
    print()


def run_type_mode(assistant_name: str):
    """Interactive command-line REPL for typing instructions."""
    from z3ro.agent import Z3ROAgent

    agent = Z3ROAgent()
    print_banner(assistant_name, mode="Keyboard CLI", engine=config.ENGINE)

    print(f"{Colors.BOLD}Type your instructions below.{Colors.RESET}")
    print(f"Commands: {Colors.CYAN}exit{Colors.RESET} / {Colors.CYAN}quit{Colors.RESET} to leave, {Colors.CYAN}doctor{Colors.RESET} to test system.\n")

    while True:
        try:
            instruction = input(f"{Colors.BOLD}{Colors.CYAN}You > {Colors.RESET}").strip()

            if not instruction:
                continue

            if instruction.lower() in ("exit", "quit", "q"):
                print(f"{Colors.GREEN}{assistant_name}: Goodbye!{Colors.RESET}")
                break

            if instruction.lower() == "doctor":
                SystemDoctor().run_all()
                continue

            print()
            results = agent.run(instruction)
            print()

            for res in results:
                print(f"{Colors.BOLD}{Colors.GREEN}{assistant_name}: {Colors.RESET}{res}")
            print()

        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}Session ended.{Colors.RESET}")
            break
        except Exception as e:
            logger.error(f"Execution error: {e}")


def run_ptt_mode(assistant_name: str):
    """Push-to-talk mode: press Enter to start/stop speaking without wake word."""
    from z3ro.agent import Z3ROAgent
    from z3ro.voice.stt import STT
    from z3ro.voice.tts import TTS

    print_banner(assistant_name, mode="Push-To-Talk", engine=config.ENGINE)
    logger.info("Initializing Push-To-Talk pipeline...")

    agent = Z3ROAgent()
    stt = STT()
    tts = TTS()

    tts.speak(f"{assistant_name} is ready in push to talk mode.")
    print(f"\n{Colors.BOLD}{Colors.GREEN}Push-To-Talk is live!{Colors.RESET}")
    print(f"Press {Colors.CYAN}[ENTER]{Colors.RESET} to record, speak your command, then press {Colors.CYAN}[ENTER]{Colors.RESET} to stop.\n")

    import sounddevice as sd
    import numpy as np

    rate = config.AUDIO_SAMPLE_RATE

    while True:
        try:
            input(f"{Colors.BOLD}Press [ENTER] to start speaking...{Colors.RESET}")
            print(f"{Colors.RED}● Recording... (Press [ENTER] when done speaking){Colors.RESET}")

            audio_chunks = []
            stop_recording = False

            def audio_callback(indata, frames, time_info, status):
                if not stop_recording:
                    audio_chunks.append(indata.copy())

            stream = sd.InputStream(
                samplerate=rate,
                channels=1,
                dtype="float32",
                callback=audio_callback,
            )

            with stream:
                input()  # Wait for Enter to stop
                stop_recording = True

            if not audio_chunks:
                print(f"{Colors.YELLOW}No audio captured.{Colors.RESET}")
                continue

            audio_data = np.concatenate(audio_chunks, axis=0).flatten()
            duration = len(audio_data) / rate
            print(f"Captured {duration:.1f}s of audio. Transcribing...")

            # Transcribe
            command = stt.transcribe(audio_data, sample_rate=rate).strip()
            if not command:
                print(f"{Colors.YELLOW}Could not hear any speech. Try again.{Colors.RESET}")
                continue

            print(f"{Colors.BOLD}{Colors.CYAN}You said:{Colors.RESET} \"{command}\"")

            if command.lower() in ("exit", "quit", "shutdown"):
                tts.speak("Goodbye.")
                break

            # Execute via Agent
            tts.speak("Working on it.")
            results = agent.run(command)

            # Summarize result via voice
            if results:
                tts.speak(results[-1])
            else:
                tts.speak("Done.")

            print()

        except KeyboardInterrupt:
            print(f"\n{Colors.YELLOW}PTT mode closed.{Colors.RESET}")
            break
        except Exception as e:
            logger.error(f"PTT loop error: {e}")


def run_voice_mode(assistant_name: str):
    """Full hands-free voice loop using wake-word, whisper STT, agent, and TTS."""
    from z3ro.main import run_voice_mode as z3ro_run_voice

    print_banner(assistant_name, mode="Hands-Free Voice", engine=config.ENGINE)
    z3ro_run_voice()


def run_cloud_live_mode(assistant_name: str):
    """SOBIA Cloud Gemini Live preview audio mode."""
    if not config.GEMINI_API_KEY and "GEMINI_API_KEY" not in os.environ:
        logger.error("GEMINI_API_KEY environment variable is not set.")
        print(f"\n{Colors.RED}Error: Cloud engine requires GEMINI_API_KEY in your .env or environment.{Colors.RESET}")
        print(f"{Colors.YELLOW}Falling back to local keyboard mode...{Colors.RESET}\n")
        run_type_mode(assistant_name)
        return

    try:
        from sobia_voice import main as sobia_voice_main
        print_banner(assistant_name, mode="Gemini Live Voice", engine="Cloud (Gemini)")
        import asyncio
        asyncio.run(sobia_voice_main())
    except Exception as e:
        logger.error(f"Cloud Live session failed: {e}")
        print(f"{Colors.YELLOW}Falling back to local keyboard mode.{Colors.RESET}")
        run_type_mode(assistant_name)


def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Unified Z3RO & SOBIA Assistant Runtime",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    parser.add_argument(
        "--name",
        type=str,
        default=config.ASSISTANT_NAME,
        help="Set the assistant name/identity (e.g. Z3RO, SOBIA, SOHAN). Default: Z3RO",
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["voice", "type", "ptt", "cloud"],
        default=None,
        help=(
            "Operational mode:\n"
            "  voice  : Hands-free wake word listening loop (default)\n"
            "  type   : Interactive keyboard CLI REPL\n"
            "  ptt    : Push-to-talk voice mode (no wake word needed)\n"
            "  cloud  : SOBIA Gemini Live streaming voice mode"
        ),
    )

    parser.add_argument(
        "--type",
        action="store_true",
        help="Quick shortcut for --mode type (keyboard CLI)",
    )

    parser.add_argument(
        "--task",
        type=str,
        default=None,
        help="Execute a single command or instruction headlessly and exit",
    )

    parser.add_argument(
        "--doctor",
        "--check",
        action="store_true",
        dest="run_doctor",
        help="Run comprehensive system health checks and pre-flight diagnostics",
    )

    parser.add_argument(
        "--no-vision",
        action="store_true",
        help="Disable vision verification to save compute and time",
    )

    args = parser.parse_args()

    # Update config dynamically based on CLI args
    config.ASSISTANT_NAME = args.name
    if args.no_vision:
        config.ENABLE_VISION_VERIFICATION = False

    # Handle graceful exit
    def sig_handler(sig, frame):
        print(f"\n{Colors.YELLOW}[*] Shutting down gracefully...{Colors.RESET}")
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)

    # 1. Run Doctor / Pre-flight check
    if args.run_doctor:
        doctor = SystemDoctor()
        passed = doctor.run_all()
        sys.exit(0 if passed else 1)

    # 2. One-shot autonomous task
    if args.task:
        print_banner(config.ASSISTANT_NAME, mode="One-Shot Task", engine=config.ENGINE)
        run_one_shot_task(args.task)
        return

    # 3. Determine selected mode
    mode = args.mode
    if args.type:
        mode = "type"
    elif mode is None:
        mode = config.DEFAULT_MODE

    # 4. Dispatch mode
    if mode == "type":
        run_type_mode(config.ASSISTANT_NAME)
    elif mode == "ptt":
        run_ptt_mode(config.ASSISTANT_NAME)
    elif mode == "cloud":
        run_cloud_live_mode(config.ASSISTANT_NAME)
    else:
        run_voice_mode(config.ASSISTANT_NAME)


if __name__ == "__main__":
    main()
