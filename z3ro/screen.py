import os
import time
from dataclasses import dataclass

import pyautogui


@dataclass
class ScreenshotResult:
    success: bool
    path: str = ""
    output: str = ""


class Screen:

    def capture(self, path: str = "z3ro_screen.png") -> ScreenshotResult:
        """Capture the current screen and save it as an image."""

        try:
            screenshot = pyautogui.screenshot()

            screenshot.save(path)

            if not os.path.exists(path):
                return ScreenshotResult(
                    success=False,
                    output="Screenshot file was not created.",
                )

            return ScreenshotResult(
                success=True,
                path=os.path.abspath(path),
                output=f"Screenshot captured: {os.path.abspath(path)}",
            )

        except Exception as e:

            return ScreenshotResult(
                success=False,
                output=f"Screenshot failed: {e}",
            )

    def wait_and_capture(
        self,
        delay: float = 0.5,
        path: str = "z3ro_screen.png",
    ) -> ScreenshotResult:
        """Wait briefly and capture the screen."""

        if delay < 0:
            delay = 0

        time.sleep(delay)

        return self.capture(path)


if __name__ == "__main__":

    print("================================")
    print("       Z3RO SCREEN SYSTEM")
    print("================================")
    print()

    screen = Screen()

    print("Capturing screen...")

    result = screen.capture()

    print(result.output)

    if result.success:
        print()
        print("Screen capture: SUCCESS")

        print()
        print("Testing delayed capture...")

        result = screen.wait_and_capture(
            delay=0.5,
        )

        print(result.output)

        if result.success:
            print("Delayed capture: SUCCESS")