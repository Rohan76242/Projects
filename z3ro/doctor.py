"""Z3RO / SOBIA — System Doctor & Health Diagnostics.

Verifies hardware, models, APIs, and OS integration to ensure the assistant
can run smoothly in production.
"""

import sys
import os
import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import List, Dict, Any

# Ensure stdout encoding safety on Windows
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

CHECK_PASS = "[OK]  "
CHECK_FAIL = "[FAIL]"

from z3ro.config import config
from z3ro.logger import Colors, logger


@dataclass
class CheckResult:
    category: str
    name: str
    passed: bool
    details: str
    remedy: str = ""


class SystemDoctor:
    """Pre-flight check suite for the AI assistant system."""

    def __init__(self):
        self.results: List[CheckResult] = []

    def check_python(self):
        """Check Python version and architecture."""
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        is_64bit = sys.maxsize > 2**32
        passed = sys.version_info >= (3, 10)
        self.results.append(
            CheckResult(
                category="Environment",
                name="Python Runtime",
                passed=passed,
                details=f"Python {py_ver} ({'64-bit' if is_64bit else '32-bit'})",
                remedy="Python 3.10+ 64-bit is recommended." if not passed else "",
            )
        )

    def check_ollama(self):
        """Check Ollama service and required models."""
        # 1. Connection check
        ollama_ok = False
        pulled_models = []
        try:
            req = urllib.request.Request(f"{config.OLLAMA_HOST}/api/tags")
            with urllib.request.urlopen(req, timeout=3) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    ollama_ok = True
                    pulled_models = [m.get("name", "") for m in data.get("models", [])]
        except Exception as e:
            ollama_ok = False

        self.results.append(
            CheckResult(
                category="AI Models",
                name="Ollama Service",
                passed=ollama_ok,
                details=f"Connected to {config.OLLAMA_HOST}" if ollama_ok else f"Failed to connect to {config.OLLAMA_HOST}",
                remedy="Start Ollama by running 'ollama serve' or launching the Ollama desktop app." if not ollama_ok else "",
            )
        )

        if ollama_ok:
            # Check Brain model
            brain_name = config.BRAIN_MODEL
            brain_match = any(brain_name in m or m.startswith(brain_name.split(":")[0]) for m in pulled_models)
            self.results.append(
                CheckResult(
                    category="AI Models",
                    name="Brain Model (Planner)",
                    passed=brain_match,
                    details=f"Model '{brain_name}' available" if brain_match else f"Model '{brain_name}' NOT found in Ollama",
                    remedy=f"Run: ollama pull {brain_name}" if not brain_match else "",
                )
            )

            # Check Vision model
            vision_name = config.VISION_MODEL
            vision_match = any(vision_name in m or m.startswith(vision_name.split(":")[0]) for m in pulled_models)
            self.results.append(
                CheckResult(
                    category="AI Models",
                    name="Vision Model (Verification)",
                    passed=vision_match,
                    details=f"Model '{vision_name}' available" if vision_match else f"Model '{vision_name}' NOT found in Ollama",
                    remedy=f"Run: ollama pull {vision_name}" if not vision_match else "",
                )
            )

    def check_audio(self):
        """Check microphone and audio devices."""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devices = [d for d in devices if d.get("max_input_channels", 0) > 0]
            output_devices = [d for d in devices if d.get("max_output_channels", 0) > 0]

            mic_ok = len(input_devices) > 0
            self.results.append(
                CheckResult(
                    category="Audio Hardware",
                    name="Microphone",
                    passed=mic_ok,
                    details=f"Detected {len(input_devices)} audio input device(s)",
                    remedy="Plug in a working microphone or configure your sound settings." if not mic_ok else "",
                )
            )

            speaker_ok = len(output_devices) > 0
            self.results.append(
                CheckResult(
                    category="Audio Hardware",
                    name="Speaker / Output",
                    passed=speaker_ok,
                    details=f"Detected {len(output_devices)} audio output device(s)",
                    remedy="Connect speakers or headphones." if not speaker_ok else "",
                )
            )
        except Exception as e:
            self.results.append(
                CheckResult(
                    category="Audio Hardware",
                    name="Sounddevice Driver",
                    passed=False,
                    details=f"Error querying audio: {e}",
                    remedy="Reinstall sounddevice / check Windows audio drivers.",
                )
            )

    def check_wakeword(self):
        """Check wake-word model presence."""
        path = config.WAKEWORD_MODEL_PATH
        exists = os.path.isfile(path)
        size_kb = os.path.getsize(path) // 1024 if exists else 0
        self.results.append(
            CheckResult(
                category="Voice Pipeline",
                name="Wake-Word CNN Model",
                passed=exists and size_kb > 10,
                details=f"Found: {os.path.basename(path)} ({size_kb} KB)" if exists else f"Missing at: {path}",
                remedy=f"Train or copy the wakeword weights to: {path}" if not exists else "",
            )
        )

    def check_screen_automation(self):
        """Check PyAutoGUI and screen capture capability."""
        try:
            import pyautogui
            size = pyautogui.size()
            passed = size[0] > 0 and size[1] > 0
            self.results.append(
                CheckResult(
                    category="OS Automation",
                    name="Display & Screen Capture",
                    passed=passed,
                    details=f"Primary resolution: {size[0]}x{size[1]}",
                    remedy="Ensure display is active and accessible." if not passed else "",
                )
            )
        except Exception as e:
            self.results.append(
                CheckResult(
                    category="OS Automation",
                    name="Display & Screen Capture",
                    passed=False,
                    details=f"Screen capture test failed: {e}",
                    remedy="Install pillow and pyautogui.",
                )
            )

    def check_app_catalog(self):
        """Check the local Start menu application catalog."""
        try:
            from z3ro.app_catalog import enabled_apps
            apps = enabled_apps()
            passed = len(apps) > 0
            self.results.append(
                CheckResult(
                    category="OS Automation",
                    name="App Catalog",
                    passed=passed,
                    details=f"{len(apps)} enabled applications registered",
                    remedy="Check z3ro/apps.txt format if empty." if not passed else "",
                )
            )
        except Exception as e:
            self.results.append(
                CheckResult(
                    category="OS Automation",
                    name="App Catalog",
                    passed=False,
                    details=f"Error reading catalog: {e}",
                    remedy="Ensure z3ro/apps.txt exists and is readable.",
                )
            )

    def run_all(self) -> bool:
        """Run all diagnostic checks and print a formatted report."""
        self.results = []
        self.check_python()
        self.check_ollama()
        self.check_audio()
        self.check_wakeword()
        self.check_screen_automation()
        self.check_app_catalog()

        print()
        print(f"{Colors.BOLD}{Colors.CYAN}======================================================{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}           SYSTEM DIAGNOSTIC REPORT (DOCTOR)          {Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}======================================================{Colors.RESET}")
        print()

        current_cat = ""
        all_passed = True

        for res in self.results:
            if res.category != current_cat:
                current_cat = res.category
                print(f"{Colors.BOLD}{Colors.WHITE}[{current_cat}]{Colors.RESET}")

            status_icon = f"{Colors.GREEN}{CHECK_PASS}{Colors.RESET}" if res.passed else f"{Colors.RED}{CHECK_FAIL}{Colors.RESET}"
            print(f"  {status_icon} {Colors.BOLD}{res.name:<26}{Colors.RESET} : {res.details}")
            if not res.passed:
                all_passed = False
                if res.remedy:
                    print(f"         {Colors.YELLOW}-> Action: {res.remedy}{Colors.RESET}")

        print()
        print(f"{Colors.BOLD}{Colors.CYAN}------------------------------------------------------{Colors.RESET}")
        if all_passed:
            print(f"{Colors.BOLD}{Colors.GREEN}[OK] All checks passed! The system is production ready.{Colors.RESET}")
        else:
            print(f"{Colors.BOLD}{Colors.YELLOW}[!] Some items need attention. See remedies above.{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}======================================================{Colors.RESET}")
        print()

        return all_passed


if __name__ == "__main__":
    doctor = SystemDoctor()
    doctor.run_all()
