from z3ro.window import focus_window
import subprocess
from dataclasses import dataclass
from typing import Callable

import pyautogui


@dataclass
class ToolResult:
    success: bool
    output: str


class Tool:
    """A controlled action that Z3RO is allowed to execute."""

    def __init__(
        self,
        name: str,
        description: str,
        function: Callable,
    ):
        self.name = name
        self.description = description
        self.function = function

    def execute(self, **kwargs) -> ToolResult:
        try:
            return self.function(**kwargs)
        except Exception as e:
            return ToolResult(
                success=False,
                output=str(e),
            )


def open_app(app: str) -> ToolResult:
    """Open an approved Windows application."""

    allowed_apps = {
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "paint": "mspaint.exe",
        "explorer": "explorer.exe",
        "chrome": r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    }

    app_key = app.lower().strip()

    if app_key not in allowed_apps:
        return ToolResult(
            success=False,
            output=f"Application '{app}' is not in the allowed app list.",
        )

    try:
        subprocess.Popen(
            [allowed_apps[app_key]],
            shell=False,
        )

        return ToolResult(
            success=True,
            output=f"Opened {app_key}.",
        )

    except FileNotFoundError:
        return ToolResult(
            success=False,
            output=f"{app_key} is not installed or could not be found.",
        )


def type_text(text: str) -> ToolResult:
    """Type controlled text into the currently focused application."""

    if not isinstance(text, str):
        return ToolResult(
            success=False,
            output="Text must be a string.",
        )

    if not text:
        return ToolResult(
            success=False,
            output="No text supplied.",
        )

    if len(text) > 2000:
        return ToolResult(
            success=False,
            output="Text is too long.",
        )

    pyautogui.write(
        text,
        interval=0.01,
    )

    return ToolResult(
        success=True,
        output="Text typed successfully.",
    )


def press_key(key: str) -> ToolResult:
    """Press one approved keyboard key."""

    allowed_keys = {
        "enter",
        "esc",
        "escape",
        "tab",
        "space",
        "backspace",
        "delete",
        "up",
        "down",
        "left",
        "right",
        "home",
        "end",
        "pageup",
        "pagedown",
    }

    key_name = key.lower().strip()

    if key_name not in allowed_keys:
        return ToolResult(
            success=False,
            output=f"Key '{key}' is not allowed.",
        )

    if key_name == "escape":
        key_name = "esc"

    pyautogui.press(key_name)

    return ToolResult(
        success=True,
        output=f"Pressed {key_name}.",
    )

def focus_app_window(title: str) -> ToolResult:
    """Focus a visible Windows application window."""

    if not isinstance(title, str) or not title.strip():
        return ToolResult(
            success=False,
            output="A window title is required.",
        )

    if len(title) > 100:
        return ToolResult(
            success=False,
            output="Window title is too long.",
        )

    if focus_window(title):
        return ToolResult(
            success=True,
            output=f"Focused window: {title}.",
        )

    return ToolResult(
        success=False,
        output=f"Could not find a visible window matching '{title}'.",
    )


TOOLS = {
    "focus_window": Tool(
        name="focus_window",
        description="Focus a visible Windows application window.",
        function=focus_app_window,
    ),

    "open_app": Tool(
        name="open_app",
        description="Open an approved Windows application.",
        function=open_app,
    ),

    "type_text": Tool(
        name="type_text",
        description="Type text into the currently focused application.",
        function=type_text,
    ),

    "press_key": Tool(
        name="press_key",
        description="Press an approved keyboard key.",
        function=press_key,
    ),
}


def execute_tool(name: str, **kwargs) -> ToolResult:
    """Execute a registered Z3RO tool."""

    tool = TOOLS.get(name)

    if tool is None:
        return ToolResult(
            success=False,
            output=f"Unknown tool: {name}",
        )

    return tool.execute(**kwargs)


if __name__ == "__main__":
    print("================================")
    print("       Z3RO TOOL ENGINE")
    print("================================")
    print()

    result = execute_tool(
        "open_app",
        app="notepad",
    )

    print(result.output)