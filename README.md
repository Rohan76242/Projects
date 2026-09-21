# 🧠 Z3RO / SOBIA — Autonomous AI Voice & Computer Control Assistant

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-0078D6.svg)](https://www.microsoft.com/windows)
[![Local AI](https://img.shields.io/badge/engine-Ollama%20Local%20%2B%20Gemini%20Cloud-orange.svg)](https://ollama.ai)

**Z3RO / SOBIA** is a production-grade, local-first voice assistant and autonomous Windows desktop agent. It combines real-time voice interaction, screen verification vision, and direct operating system automation into a unified, secure platform.

---

## 🌟 Key Capabilities

- **🎙️ Real-time Voice Pipeline**:
  - Offline wake-word detection powered by a custom PyTorch CNN.
  - Speech-to-Text via `faster-whisper` (int8 quantized for low latency).
  - Offline natural voice synthesis via `pyttsx3`.
- **🧠 Local Neural Brain**:
  - Fast, grounded reasoning via Ollama (`qwen2.5:1.5b-instruct`).
  - Structured JSON action planner with fail-safe sanitization and validation.
- **👁️ Visual Verification**:
  - Screen state verification using `moondream:latest` vision model.
  - Confirms application launches and state transitions before declaring success.
- **💻 Full Windows Desktop Grounding**:
  - Start Menu App Catalog (75+ catalogued native Windows applications).
  - Window focus, maximize, minimize, restore, and safe process closing.
  - Controlled mouse actions and automated keyboard typing.
- **☁️ Cloud Multimodal Support (SOBIA)**:
  - Optional streaming voice interaction powered by Google Gemini Live preview.
- **🩺 Pre-Flight Diagnostics (Doctor)**:
  - Comprehensive health-check engine verifying audio devices, Ollama models, display, and permissions.

---

## 🏗️ Architecture

```
                                  [ User ]
                                     │
                 ┌───────────────────┴───────────────────┐
                 ▼                                       ▼
        [ Microphone Input ]                    [ Keyboard / CLI ]
                 │                                       │
     [ PyTorch Wake Word CNN ]                           │
                 │                                       │
      [ faster-whisper STT ]                             │
                 │                                       │
                 └───────────────────┬───────────────────┘
                                     ▼
                            ┌────────────────┐
                            │    name.py     │  ◄── Unified Master Runtime
                            └───────┬────────┘
                                    │
                 ┌──────────────────┴──────────────────┐
                 ▼                                     ▼
      [ Local Ollama Brain ]                  [ SOBIA Cloud Live ]
     (qwen2.5:1.5b-instruct)                  (Gemini 3.1 Live)
                 │
                 ▼
      [ Structured Planner ]
                 │
        ┌────────┴────────┐
        ▼                 ▼
[ Windows Tools ]   [ Vision Verification ]
• App Catalog       (moondream:latest)
• Window Manager
• Keyboard / Mouse
        │
        ▼
   [ pyttsx3 TTS ] ──► [ Speaker Audio ]
```

---

## ⚡ Quick Start

### 1. Prerequisites

1. **Python 3.10+ (64-bit)**
2. **[Ollama](https://ollama.com/)** installed and running.
3. Download the local models:
   ```bash
   ollama pull qwen2.5:1.5b-instruct
   ollama pull moondream:latest
   ```

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/Rohan76242/Projects.git
cd Projects

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Run Pre-Flight Diagnostic Health Check

Before starting, run the built-in system doctor to ensure all hardware and models are configured:
```bash
python name.py --doctor
```

---

## 🚀 Usage Modes

The unified entry point `name.py` connects all subsystems:

### 1. Interactive Keyboard Mode (Recommended for testing)
Test planning, app launching, and tool execution without needing a microphone:
```bash
python name.py --mode type
# or shortcut:
python name.py --type
```

### 2. Hands-Free Voice Mode (Wake Word)
Full voice loop: Say the wake word to activate, speak your instruction, and receive spoken confirmation:
```bash
python name.py --mode voice
```

### 3. Push-To-Talk (PTT) Mode
Instant voice control without wake-word false triggers. Press `[ENTER]` to speak, and press `[ENTER]` when done:
```bash
python name.py --mode ptt
```

### 4. Autonomous One-Shot Task
Execute a single instruction headlessly from the command line:
```bash
python name.py --task "open notepad"
python name.py --task "list windows"
```

### 5. Identity Switcher (SOBIA / Z3RO)
Switch personality, banners, and identity prompts seamlessly:
```bash
python name.py --name SOBIA --mode type
python name.py --name Z3RO --mode voice
```

---

## ⚙️ Configuration

Copy `.env.example` to `.env` to customize settings:
```bash
cp .env.example .env
```

| Variable | Default | Description |
| :--- | :--- | :--- |
| `ASSISTANT_NAME` | `Z3RO` | Identity name displayed and spoken |
| `DEFAULT_MODE` | `voice` | Default startup mode (`voice`, `type`, `ptt`, `cloud`) |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama API endpoint |
| `BRAIN_MODEL` | `qwen2.5:1.5b-instruct` | Primary reasoning / planning LLM |
| `VISION_MODEL` | `moondream:latest` | Vision verification model |
| `STT_MODEL_SIZE` | `base.en` | Whisper model size (`tiny.en`, `base.en`, `small.en`) |
| `TTS_RATE` | `180` | Speech synthesis speed (WPM) |
| `LOG_LEVEL` | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `GEMINI_API_KEY` | *(Optional)* | Required only if running SOBIA Cloud Live mode |

---

## 🛡️ Tool Safety & Grounding

Z3RO executes actions through an approved registry:
- **Application Launching**: Only executes apps verified against [`z3ro/apps.txt`](file:///c:/sobia/Projects/z3ro/apps.txt). Blocked applications (e.g. terminals, dangerous binaries) are strictly prevented.
- **Fail-Safe Window Control**: Window focus, restore, and closure require exact or validated window titles.
- **Visual Feedback**: Vision verification confirms the intended state change occurred before marking tasks complete.

---

## 🧪 Testing

Run the automated test suite:
```bash
python -m unittest discover -s tests
```

---

## 📄 License

MIT License. Developed for autonomous local Windows interaction and voice assistance.
