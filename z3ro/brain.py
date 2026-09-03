import json
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Optional


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "qwen3:1.7b"


SYSTEM_PROMPT = """
You are Z3RO, a personal AI computer assistant.

Answer the user's request directly and concisely.
Do not pretend that you performed actions you did not perform.
Do not expose internal reasoning.
"""


@dataclass
class BrainResponse:
    text: str
    success: bool = True
    error: Optional[str] = None


class Brain:
    def think(self, prompt: str) -> BrainResponse:
        raise NotImplementedError


class LocalBrain(Brain):

    def __init__(self, model: str = MODEL):
        self.model = model

    def think(self, prompt: str) -> BrainResponse:

        payload = {
            "model": self.model,
            "system": SYSTEM_PROMPT,
            "prompt": prompt,
            "stream": False,
            "think": False,
        }

        try:
            request = urllib.request.Request(
                OLLAMA_URL,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )

            with urllib.request.urlopen(request, timeout=120) as response:
                data = json.loads(response.read().decode("utf-8"))

            text = data.get("response", "").strip()

            if not text:
                return BrainResponse(
                    text="",
                    success=False,
                    error="Ollama returned an empty response.",
                )

            return BrainResponse(text=text)

        except urllib.error.HTTPError as e:
            return BrainResponse(
                text="",
                success=False,
                error=f"Ollama HTTP {e.code}: {e.reason}",
            )

        except urllib.error.URLError as e:
            return BrainResponse(
                text="",
                success=False,
                error=f"Could not connect to Ollama: {e.reason}",
            )

        except Exception as e:
            return BrainResponse(
                text="",
                success=False,
                error=str(e),
            )


if __name__ == "__main__":

    brain = LocalBrain()

    print("================================")
    print("       Z3RO BRAIN ONLINE")
    print("================================")
    print(f"Model: {MODEL}")
    print("Runtime: Ollama")
    print()

    response = brain.think(
        "Reply with exactly three words: Z3RO IS ONLINE"
    )

    if response.success:
        print("Z3RO:", response.text)
    else:
        print("ERROR:", response.error)