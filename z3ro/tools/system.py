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

    # 1. Native Standalone Desktop Apps (YouTube standalone app, WhatsApp, Telegram)
    if lower_query in ("youtube", "yt", "you tube") or "youtube" in lower_query:
        youtube_lnk = os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs\Chrome Apps\YouTube.lnk")
        if os.path.isfile(youtube_lnk):
            try:
                os.startfile(youtube_lnk)
                return ToolResult(
                    success=True,
                    output="Opened YouTube.",
                )
            except Exception:
                pass

    if lower_query in ("whatsapp", "whats app", "wa"):
        from z3ro.messaging.whatsapp import open_whatsapp
        res = open_whatsapp()
        return ToolResult(
            success=res["success"],
            output=res["output"],
        )

    if lower_query in ("telegram", "tele gram", "tg"):
        from z3ro.messaging.telegram import open_telegram
        res = open_telegram()
        return ToolResult(
            success=res["success"],
            output=res["output"],
        )

    # 2. Direct Web Platforms & Services (Google, Reddit, etc.)
    WEB_PLATFORMS = {
        "google": ("Google", "https://www.google.com"),
        "github": ("GitHub", "https://www.github.com"),
        "reddit": ("Reddit", "https://www.reddit.com"),
        "chatgpt": ("ChatGPT", "https://chatgpt.com"),
        "gmail": ("Gmail", "https://mail.google.com"),
        "netflix": ("Netflix", "https://www.netflix.com"),
        "twitch": ("Twitch", "https://www.twitch.tv"),
        "twitter": ("Twitter", "https://x.com"),
        "x": ("X", "https://x.com"),
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

    # 3. Direct URLs or Domain Requests
    if lower_query.startswith(("http://", "https://", "www.")) or (
        "." in lower_query and any(lower_query.endswith(ext) for ext in (".com", ".org", ".net", ".io", ".tv", ".ai", ".co"))
    ):
        url = clean_query if clean_query.startswith(("http://", "https://")) else f"https://{clean_query}"
        webbrowser.open(url)
        return ToolResult(
            success=True,
            output=f"Opened {clean_query}.",
        )

    # 4. Local Desktop Applications Registry Lookup
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

    # 5. Launch Local Executable, UWP App, or System Utility
    lower_target = target_path.lower()
    try:
        if lower_target.startswith("shell:appsfolder\\") or (catalog_app and catalog_app.kind == "app_id"):
            uwp_target = target_path if target_path.lower().startswith("shell:") else f"shell:AppsFolder\\{target_path}"
            subprocess.Popen(["explorer.exe", uwp_target])
        elif lower_target.endswith(".msc"):
            subprocess.Popen(["mmc.exe", target_path])
        elif lower_target.endswith(".cpl"):
            subprocess.Popen(["control.exe", target_path])
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


def send_whatsapp_tool(recipient: str = "", message: str = "", **kwargs) -> ToolResult:
    """Send a WhatsApp message to a contact or phone number."""
    from z3ro.messaging.whatsapp import send_whatsapp
    recip = recipient or kwargs.get("contact") or kwargs.get("to") or kwargs.get("phone", "")
    msg = message or kwargs.get("text", "")
    res = send_whatsapp(recip, msg)
    return ToolResult(success=res["success"], output=res["output"])


def open_whatsapp_tool(**kwargs) -> ToolResult:
    """Open WhatsApp Desktop application."""
    from z3ro.messaging.whatsapp import open_whatsapp
    res = open_whatsapp()
    return ToolResult(success=res["success"], output=res["output"])


def send_telegram_tool(recipient: str = "", message: str = "", **kwargs) -> ToolResult:
    """Send a Telegram message to a contact, username, or chat."""
    from z3ro.messaging.telegram import send_telegram
    recip = recipient or kwargs.get("contact") or kwargs.get("to") or kwargs.get("username", "")
    msg = message or kwargs.get("text", "")
    res = send_telegram(recip, msg)
    return ToolResult(success=res["success"], output=res["output"])


def open_telegram_tool(**kwargs) -> ToolResult:
    """Open Telegram Desktop application."""
    from z3ro.messaging.telegram import open_telegram
    res = open_telegram()
    return ToolResult(success=res["success"], output=res["output"])


def get_youtube_video(query: str) -> str | None:
    """Search YouTube and return the top video ID."""
    import urllib.request
    import urllib.parse
    import re

    clean = query.strip()
    if not clean:
        clean = "top hits songs"

    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(clean)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        ids = re.findall(r"watch\?v=([a-zA-Z0-9_-]{11})", html)
        if ids:
            return ids[0]
    except Exception:
        pass
    return None


def play_song(song: str = "", **kwargs) -> ToolResult:
    """Search and play a song or music video on YouTube in standalone app mode."""
    import os
    import shutil
    import subprocess
    import webbrowser

    raw_query = song or kwargs.get("query") or kwargs.get("title") or kwargs.get("text") or ""
    clean_query = str(raw_query).strip()

    # Strip prefixes like "play ", "a song", "on youtube"
    for prefix in ("play ", "song ", "music ", "search "):
        if clean_query.lower().startswith(prefix):
            clean_query = clean_query[len(prefix):].strip()

    for suffix in (" on youtube", " in youtube", " song", " music"):
        if clean_query.lower().endswith(suffix):
            clean_query = clean_query[:-len(suffix)].strip()

    if not clean_query or clean_query.lower() in ("a song", "song", "music", "something", "any song"):
        display_title = "popular music"
        search_term = "top trending hits songs"
    else:
        display_title = clean_query
        search_term = f"{clean_query} song"

    # 1. Fetch top video ID
    video_id = get_youtube_video(search_term)
    if video_id:
        target_url = f"https://www.youtube.com/watch?v={video_id}"
    else:
        import urllib.parse
        target_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(search_term)}"

    # 2. Launch in standalone YouTube app window (Chrome --app=URL)
    chrome_candidates = [
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        shutil.which("chrome.exe"),
        shutil.which("chrome"),
    ]
    chrome_exe = next((p for p in chrome_candidates if p and os.path.isfile(p)), None)

    try:
        if chrome_exe:
            # Opens in a clean standalone window without browser address bar
            subprocess.Popen([chrome_exe, f"--app={target_url}"])
        else:
            webbrowser.open(target_url)

        return ToolResult(
            success=True,
            output=f"Playing {display_title} on YouTube.",
        )
    except Exception as e:
        try:
            webbrowser.open(target_url)
            return ToolResult(
                success=True,
                output=f"Playing {display_title} on YouTube.",
            )
        except Exception as err:
            return ToolResult(
                success=False,
                output=f"Failed to play song: {err}",
            )


TOOLS = {

    "open_app": Tool(
        name="open_app",
        description=(
            "Open an approved Windows application."
        ),
        function=open_app,
    ),

    "play_song": Tool(
        name="play_song",
        description="Search and play a song or music video on YouTube in standalone app mode.",
        function=play_song,
    ),

    "send_whatsapp": Tool(
        name="send_whatsapp",
        description="Send a message to a WhatsApp contact or phone number.",
        function=send_whatsapp_tool,
    ),

    "open_whatsapp": Tool(
        name="open_whatsapp",
        description="Open the native WhatsApp desktop application.",
        function=open_whatsapp_tool,
    ),

    "send_telegram": Tool(
        name="send_telegram",
        description="Send a message to a Telegram contact, username, or chat.",
        function=send_telegram_tool,
    ),

    "open_telegram": Tool(
        name="open_telegram",
        description="Open the native Telegram desktop application.",
        function=open_telegram_tool,
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
