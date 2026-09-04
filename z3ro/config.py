"""Z3RO / SOBIA — Centralized Configuration System.

Loads settings from environment variables and .env file with production-ready
defaults and type validation.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Project Root Directory
BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(env_path: Path):
    """Simple parser for .env files without requiring external dotenv library."""
    if not env_path.is_file():
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("\"'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


# Automatically load .env if present
_load_env_file(BASE_DIR / ".env")


@dataclass
class Config:
    """Production configuration parameters for the assistant."""

    # Identity & Naming
    ASSISTANT_NAME: str = field(
        default_factory=lambda: os.getenv("ASSISTANT_NAME", "Z3RO")
    )
    DEFAULT_MODE: str = field(
        default_factory=lambda: os.getenv("DEFAULT_MODE", "voice")
    )
    ENGINE: str = field(
        default_factory=lambda: os.getenv("ENGINE", "local")  # local | cloud | hybrid
    )

    # Local Ollama AI Models
    OLLAMA_HOST: str = field(
        default_factory=lambda: os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    )
    BRAIN_MODEL: str = field(
        default_factory=lambda: os.getenv("BRAIN_MODEL", "qwen2.5:1.5b-instruct")
    )
    VISION_MODEL: str = field(
        default_factory=lambda: os.getenv("VISION_MODEL", "moondream:latest")
    )
    NUM_PREDICT: int = field(
        default_factory=lambda: int(os.getenv("NUM_PREDICT", "700"))
    )
    NUM_CTX: int = field(
        default_factory=lambda: int(os.getenv("NUM_CTX", "2048"))
    )

    # Cloud GenAI (Gemini / SOBIA live preview)
    GEMINI_API_KEY: Optional[str] = field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY")
    )
    GEMINI_MODEL: str = field(
        default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-3.1-flash-live-preview")
    )

    # Audio & Voice Processing
    AUDIO_SAMPLE_RATE: int = field(
        default_factory=lambda: int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
    )
    MIC_DEVICE_INDEX: Optional[int] = field(
        default_factory=lambda: (
            int(os.getenv("MIC_DEVICE_INDEX"))
            if os.getenv("MIC_DEVICE_INDEX") is not None
            else None
        )
    )
    WAKEWORD_MODEL_PATH: str = field(
        default_factory=lambda: os.getenv(
            "WAKEWORD_MODEL_PATH",
            str(BASE_DIR / "wakeword_model.pth"),
        )
    )
    WAKEWORD_THRESHOLD: float = field(
        default_factory=lambda: float(os.getenv("WAKEWORD_THRESHOLD", "0.50"))
    )

    # Speech to Text (Whisper)
    STT_MODEL_SIZE: str = field(
        default_factory=lambda: os.getenv("STT_MODEL_SIZE", "small")
    )
    STT_DEVICE: str = field(
        default_factory=lambda: os.getenv("STT_DEVICE", "cpu")
    )
    STT_COMPUTE_TYPE: str = field(
        default_factory=lambda: os.getenv("STT_COMPUTE_TYPE", "int8")
    )

    # Text to Speech (pyttsx3)
    TTS_RATE: int = field(
        default_factory=lambda: int(os.getenv("TTS_RATE", "180"))
    )
    TTS_VOLUME: float = field(
        default_factory=lambda: float(os.getenv("TTS_VOLUME", "0.9"))
    )
    TTS_VOICE_INDEX: int = field(
        default_factory=lambda: int(os.getenv("TTS_VOICE_INDEX", "0"))
    )

    # Agent & Tool Execution
    MAX_AGENT_STEPS: int = field(
        default_factory=lambda: int(os.getenv("MAX_AGENT_STEPS", "6"))
    )
    ACTION_DELAY: float = field(
        default_factory=lambda: float(os.getenv("ACTION_DELAY", "0.5"))
    )
    ENABLE_VISION_VERIFICATION: bool = field(
        default_factory=lambda: os.getenv("ENABLE_VISION_VERIFICATION", "true").lower()
        in ("1", "true", "yes")
    )

    # Paths & Logging
    LOG_DIR: Path = field(default_factory=lambda: BASE_DIR / "logs")
    LOG_LEVEL: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO").upper()
    )
    SCREENSHOT_DIR: Path = field(
        default_factory=lambda: BASE_DIR / "z3ro_screen.png"
    )

    def __post_init__(self):
        # Ensure log directory exists
        self.LOG_DIR.mkdir(parents=True, exist_ok=True)


# Global singleton instance
config = Config()
