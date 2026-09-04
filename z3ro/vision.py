import base64
import io
import json
import urllib.request
from dataclasses import dataclass

import pyautogui
from PIL import Image

from z3ro.screen import Screen


OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
MODEL = "moondream:latest"

# Max width/height we resize screenshots to before sending to the model.
# Smaller image = fewer prompt tokens = faster response.
MAX_IMAGE_DIMENSION = 640

# Enough tokens for the model's "thinking" plus a real answer.
# Too low and the response comes back empty (cut off mid-thought).
NUM_PREDICT = 400

# Context window. Doesn't need to be huge for a single screenshot + prompt.
NUM_CTX = 2048


@dataclass
class VisionResult:
    success: bool
    response: str = ""
    error: str = ""


@dataclass
class UIElement:
    found: bool
    name: str
    x: int | None
    y: int | None


class Vision:
    """Z3RO's local visual intelligence system."""

    def __init__(self):
        self.screen = Screen()

    def _ask(
        self,
        prompt: str,
        screenshot_path: str = "z3ro_screen.png",
    ) -> VisionResult:

        try:
            screenshot = self.screen.capture(
                screenshot_path
            )

            if not screenshot.success:
                return VisionResult(
                    success=False,
                    error=screenshot.output,
                )

            # Resize before encoding — this is the main lever for latency.
            # A full-resolution screenshot sends far more image tokens to
            # the model than it needs for UI grounding.
            with Image.open(screenshot.path) as img:
                img = img.convert("RGB")
                img.thumbnail(
                    (MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION)
                )

                buffer = io.BytesIO()
                img.save(buffer, format="PNG")
                image_data = base64.b64encode(
                    buffer.getvalue()
                ).decode("utf-8")

            payload = {
                "model": MODEL,
                "prompt": prompt,
                "images": [image_data],
                "stream": False,
                "options": {
                    "num_predict": NUM_PREDICT,
                    "num_ctx": NUM_CTX,
                },
            }

            data = json.dumps(
                payload
            ).encode("utf-8")

            request = urllib.request.Request(
                OLLAMA_URL,
                data=data,
                headers={
                    "Content-Type": "application/json"
                },
                method="POST",
            )

            with urllib.request.urlopen(
                request,
                timeout=60,
            ) as response:

                raw_response = (
                    response.read()
                    .decode("utf-8")
                )

            if not raw_response.strip():
                return VisionResult(
                    success=False,
                    error="Ollama returned an empty response.",
                )

            result = json.loads(
                raw_response
            )

            vision_response = str(
                result.get(
                    "response",
                    "",
                )
            ).strip()

            if not vision_response:
                return VisionResult(
                    success=False,
                    error="Vision model returned an empty response.",
                )

            return VisionResult(
                success=True,
                response=vision_response,
            )

        except Exception as e:

            return VisionResult(
                success=False,
                error=str(e),
            )

    def analyze(
        self,
        prompt: str = (
            "Describe what is visible on this screenshot. "
            "Be concise."
        ),
    ) -> VisionResult:

        return self._ask(
            prompt=prompt
        )

    def find_element(
        self,
        element_name: str,
    ) -> UIElement:
        """Find a visible UI element."""

        prompt = f"""
You are Z3RO's visual UI detection system.

Look carefully at the screenshot.

Find this UI element:

{element_name}

Return ONLY valid JSON.

The JSON must contain:

- found: true or false
- name: the element name
- x: the actual horizontal screen coordinate
- y: the actual vertical screen coordinate

The x and y coordinates must be the approximate CENTER
of the requested element.

IMPORTANT:

Do NOT use placeholder coordinates.

Do NOT automatically choose 500 for x.

Do NOT automatically choose 300 for y.

Estimate the actual position of the element from the
screenshot.

The coordinates are absolute screen pixel coordinates,
starting from the top-left corner of the screen.

If you cannot confidently locate the element, return:

{{
    "found": false,
    "name": "{element_name}",
    "x": null,
    "y": null
}}

Return JSON only.
No markdown.
No explanation.
"""

        result = self._ask(
            prompt=prompt
        )

        if not result.success:

            return UIElement(
                found=False,
                name=element_name,
                x=None,
                y=None,
            )

        try:

            text = result.response.strip()

            if text.startswith("```"):

                text = text.replace(
                    "```json",
                    "",
                )

                text = text.replace(
                    "```",
                    "",
                )

                text = text.strip()

            data = json.loads(
                text
            )

            found = bool(
                data.get(
                    "found",
                    False,
                )
            )

            x = data.get("x")
            y = data.get("y")

            if x is not None:
                x = int(x)

            if y is not None:
                y = int(y)

            return UIElement(
                found=found,
                name=str(
                    data.get(
                        "name",
                        element_name,
                    )
                ),
                x=x,
                y=y,
            )

        except Exception:

            return UIElement(
                found=False,
                name=element_name,
                x=None,
                y=None,
            )

    def find_safe_coordinate(
        self,
        element_name: str,
    ) -> UIElement:
        """Find an element and validate its coordinates."""

        element = self.find_element(
            element_name
        )

        if not element.found:
            return element

        if (
            element.x is None
            or element.y is None
        ):

            return UIElement(
                found=False,
                name=element_name,
                x=None,
                y=None,
            )

        screen_width, screen_height = (
            pyautogui.size()
        )

        if (
            element.x < 0
            or element.y < 0
            or element.x >= screen_width
            or element.y >= screen_height
        ):

            return UIElement(
                found=False,
                name=element_name,
                x=None,
                y=None,
            )

        return element


if __name__ == "__main__":

    print("================================")
    print("     Z3RO GUI GROUNDING")
    print("================================")
    print()

    vision = Vision()

    target = input(
        "Element to find: "
    ).strip()

    if not target:

        print(
            "No element supplied."
        )

        raise SystemExit(1)

    print()
    print(
        "Looking at the screen..."
    )
    print()

    element = vision.find_safe_coordinate(
        target
    )

    if element.found:

        print("FOUND:")
        print(
            f"Name: {element.name}"
        )
        print(
            f"Coordinate: "
            f"({element.x}, {element.y})"
        )

        print()
        print(
            "Coordinate validation: SUCCESS"
        )

    else:

        print(
            f"Could not safely locate: "
            f"{target}"
        )
