from dataclasses import dataclass
from typing import Callable
import subprocess

import pyautogui

from z3ro.app_catalog import (
    enabled_apps,
    find_app,
)
from z3ro.window import (
    focus_window,
    list_windows,
)


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


def open_app(
    app: str,
) -> ToolResult:
    """Open any application, driver tool, executable, or web service."""
    import os
    import shutil
    import webbrowser

    if not isinstance(app, str) or not app.strip():
        return ToolResult(
            success=False,
            output="Application name must be a non-empty string.",
        )

    clean_query = app.strip()
    lower_query = clean_query.lower()

    # 1. Direct Web Platforms & Services (YouTube, Google, Reddit, etc.)
    WEB_PLATFORMS = {
        "youtube": ("YouTube", "https://www.youtube.com"),
        "yt": ("YouTube", "https://www.youtube.com"),
        "you tube": ("YouTube", "https://www.youtube.com"),
        "google": ("Google", "https://www.google.com"),
        "github": ("GitHub", "https://www.github.com"),
        "reddit": ("Reddit", "https://www.reddit.com"),
        "chatgpt": ("ChatGPT", "https://chatgpt.com"),
        "gmail": ("Gmail", "https://mail.google.com"),
        "netflix": ("Netflix", "https://www.netflix.com"),
        "twitch": ("Twitch", "https://www.twitch.tv"),
        "twitter": ("Twitter", "https://x.com"),
        "x": ("X", "https://x.com"),
        "whatsapp": ("WhatsApp", "https://web.whatsapp.com"),
        "amazon": ("Amazon", "https://www.amazon.com"),
        "spotify web": ("Spotify", "https://open.spotify.com"),
        "wikipedia": ("Wikipedia", "https://www.wikipedia.org"),
    }

    if lower_query in WEB_PLATFORMS:
        name, url = WEB_PLATFORMS[lower_query]
        webbrowser.open(url)
        return ToolResult(
            success=True,
            output=f"Opened {name}.",
        )

    # 2. Direct URLs or Domain Requests
    if lower_query.startswith(("http://", "https://", "www.")) or (
        "." in lower_query and any(lower_query.endswith(ext) for ext in (".com", ".org", ".net", ".io", ".tv", ".ai", ".co"))
    ):
        url = clean_query if clean_query.startswith(("http://", "https://")) else f"https://{clean_query}"
        webbrowser.open(url)
        return ToolResult(
            success=True,
            output=f"Opened {clean_query}.",
        )

    # 3. Local Desktop Applications Registry Lookup
    catalog_app = find_app(clean_query)
    target_path = None
    app_name = clean_query

    if catalog_app is not None:
        target_path = catalog_app.target
        app_name = catalog_app.name
    elif os.path.isfile(clean_query):
        target_path = clean_query
    else:
        # Fallback to system PATH lookup
        found_bin = shutil.which(clean_query) or shutil.which(f"{clean_query}.exe")
        if found_bin:
            target_path = found_bin

    if not target_path:
        available_count = len(enabled_apps())
        return ToolResult(
            success=False,
            output=(
                f"Application '{clean_query}' was not found in apps.txt "
                f"({available_count} applications and tools available)."
            ),
        )

    # 4. Handle chrome_proxy web apps (e.g. YouTube PWA shortcut)
    lower_target = target_path.lower()
    if lower_target.endswith("chrome_proxy.exe"):
        if "youtube" in app_name.lower() or "youtube" in lower_query:
            webbrowser.open("https://www.youtube.com")
            return ToolResult(
                success=True,
                output="Opened YouTube.",
            )

    # 5. Launch Local Executable or System Utility
    try:
        if lower_target.endswith(".msc"):
            subprocess.Popen(["mmc.exe", target_path])
        elif lower_target.endswith(".cpl"):
            subprocess.Popen(["control.exe", target_path])
        elif catalog_app and catalog_app.kind == "app_id":
            subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{target_path}"])
        else:
            try:
                os.startfile(target_path)
            except Exception:
                subprocess.Popen([target_path], shell=False)

        # Output friendly name ONLY — never speak raw file path!
        return ToolResult(
            success=True,
            output=f"Opened {app_name}.",
        )

    except Exception as e:
        return ToolResult(
            success=False,
            output=f"Failed to launch {app_name}: {e}",
        )




def find_window_tool(
    title: str,
) -> ToolResult:
    """Find a visible Windows window and return its real center."""

    if not isinstance(title, str):

        return ToolResult(
            success=False,
            output="Window title must be a string.",
        )

    search = title.strip().lower()

    if not search:

        return ToolResult(
            success=False,
            output="Window title cannot be empty.",
        )

    try:

        windows = list_windows()

    except Exception as e:

        return ToolResult(
            success=False,
            output=(
                f"Could not enumerate windows: {e}"
            ),
        )

    # First: exact title match.
    for window in windows:

        if window.title.strip().lower() == search:

            x, y = window.center

            return ToolResult(
                success=True,
                output=(
                    f"Found '{window.title}'. "
                    f"Center: ({x}, {y})"
                ),
            )

    # Second: substring match.
    for window in windows:

        if search in window.title.lower():

            x, y = window.center

            return ToolResult(
                success=True,
                output=(
                    f"Found '{window.title}'. "
                    f"Center: ({x}, {y})"
                ),
            )

    # Third: common application-name matching.
    aliases = {
        "notepad": "notepad",
        "calculator": "calculator",
        "calc": "calculator",
        "paint": "paint",
        "explorer": "explorer",
        "chrome": "chrome",
    }

    normalized = aliases.get(
        search,
        search,
    )

    if normalized != search:

        for window in windows:

            if normalized in window.title.lower():

                x, y = window.center

                return ToolResult(
                    success=True,
                    output=(
                        f"Found '{window.title}'. "
                        f"Center: ({x}, {y})"
                    ),
                )

    return ToolResult(
        success=False,
        output=(
            f"Could not find window: {title}"
        ),
    )


def focus_app_window(
    title: str,
) -> ToolResult:
    """Focus a visible Windows application window."""

    if not isinstance(title, str):

        return ToolResult(
            success=False,
            output="Window title must be a string.",
        )

    title = title.strip()

    if not title:

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
        output=(
            f"Could not focus window: {title}"
        ),
    )


def move_mouse(
    x: int,
    y: int,
) -> ToolResult:
    """Move the mouse and verify its final position."""

    if not isinstance(x, int) or not isinstance(y, int):

        return ToolResult(
            success=False,
            output=(
                "Mouse coordinates "
                "must be integers."
            ),
        )

    screen_width, screen_height = pyautogui.size()

    if (
        x < 0
        or y < 0
        or x >= screen_width
        or y >= screen_height
    ):

        return ToolResult(
            success=False,
            output=(
                f"Coordinates outside screen: "
                f"{screen_width}x{screen_height}."
            ),
        )

    pyautogui.moveTo(
        x,
        y,
        duration=0.2,
    )

    actual_x, actual_y = pyautogui.position()

    if (
        actual_x != x
        or actual_y != y
    ):

        return ToolResult(
            success=False,
            output=(
                "Mouse verification failed. "
                f"Expected ({x}, {y}), "
                f"got ({actual_x}, {actual_y})."
            ),
        )

    return ToolResult(
        success=True,
        output=(
            f"Mouse moved and verified "
            f"at ({actual_x}, {actual_y})."
        ),
    )


def click_mouse(
    button: str = "left",
) -> ToolResult:
    """Click using an approved mouse button."""

    allowed_buttons = {
        "left",
        "right",
        "middle",
    }

    if not isinstance(button, str):

        return ToolResult(
            success=False,
            output="Mouse button must be a string.",
        )

    button_name = button.lower().strip()

    if button_name not in allowed_buttons:

        return ToolResult(
            success=False,
            output=(
                f"Mouse button '{button}' "
                "is not allowed."
            ),
        )

    pyautogui.click(
        button=button_name
    )

    return ToolResult(
        success=True,
        output=(
            f"Clicked {button_name} "
            "mouse button."
        ),
    )


def double_click_mouse() -> ToolResult:
    """Double-click using the left mouse button."""

    pyautogui.doubleClick()

    return ToolResult(
        success=True,
        output="Double-clicked.",
    )


def type_text(
    text: str,
) -> ToolResult:
    """Type controlled text."""

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


def press_key(
    key: str,
) -> ToolResult:
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

    if not isinstance(key, str):

        return ToolResult(
            success=False,
            output="Key must be a string.",
        )

    key_name = key.lower().strip()

    if key_name not in allowed_keys:

        return ToolResult(
            success=False,
            output=(
                f"Key '{key}' "
                "is not allowed."
            ),
        )

    if key_name == "escape":
        key_name = "esc"

    pyautogui.press(
        key_name
    )

    return ToolResult(
        success=True,
        output=f"Pressed {key_name}.",
    )


TOOLS = {

    "open_app": Tool(
        name="open_app",
        description=(
            "Open an approved Windows application."
        ),
        function=open_app,
    ),

    "find_window": Tool(
        name="find_window",
        description=(
            "Find a visible Windows window "
            "and return its real screen center."
        ),
        function=find_window_tool,
    ),

    "focus_window": Tool(
        name="focus_window",
        description=(
            "Focus a visible Windows application window."
        ),
        function=focus_app_window,
    ),

    "type_text": Tool(
        name="type_text",
        description=(
            "Type text into the focused application."
        ),
        function=type_text,
    ),

    "press_key": Tool(
        name="press_key",
        description=(
            "Press an approved keyboard key."
        ),
        function=press_key,
    ),

    "move_mouse": Tool(
        name="move_mouse",
        description=(
            "Move the mouse to a screen coordinate."
        ),
        function=move_mouse,
    ),

    "click_mouse": Tool(
        name="click_mouse",
        description=(
            "Click the mouse using an approved button."
        ),
        function=click_mouse,
    ),

    "double_click_mouse": Tool(
        name="double_click_mouse",
        description=(
            "Double-click using the left mouse button."
        ),
        function=double_click_mouse,
    ),
}


def execute_tool(
    name: str,
    **kwargs,
) -> ToolResult:
    """Execute a registered Z3RO tool."""

    tool = TOOLS.get(name)

    if tool is None:

        return ToolResult(
            success=False,
            output=f"Unknown tool: {name}",
        )

    return tool.execute(
        **kwargs
    )


if __name__ == "__main__":

    print("================================")
    print("       Z3RO TOOL ENGINE")
    print("================================")
    print()

    result = execute_tool(
        "find_window",
        title="Notepad",
    )

    print(result.output)
