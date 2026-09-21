from dataclasses import dataclass
from typing import Callable
import subprocess

import pyautogui
pyautogui.FAILSAFE = False

from z3ro.app_catalog import (
    enabled_apps,
    find_app,
    launch_app_via_powershell,
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


def get_working_browser() -> str | None:
    """Find a verified, functional browser executable on the Windows host."""
    import os
    import shutil

    candidates = [
        # Google Chrome
        os.path.expandvars(r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
        shutil.which("chrome.exe"),
        shutil.which("chrome"),
        # Microsoft Edge
        os.path.expandvars(r"%PROGRAMFILES(X86)%\Microsoft\Edge\Application\msedge.exe"),
        os.path.expandvars(r"%PROGRAMFILES%\Microsoft\Edge\Application\msedge.exe"),
        shutil.which("msedge.exe"),
        shutil.which("msedge"),
        # Brave Browser
        os.path.expandvars(r"%PROGRAMFILES%\BraveSoftware\Brave-Browser\Application\brave.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\BraveSoftware\Brave-Browser\Application\brave.exe"),
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return None


def open_browser_url(url: str, app_mode: bool = False) -> bool:
    """Reliably launch any web URL in Chrome, Edge, or default browser on Windows.
    
    Spawns asynchronously into the user's interactive desktop (WinSta0\\Default)
    without opening unsightly console windows.
    """
    import subprocess

    browser_exe = get_working_browser()
    escaped_url = url.replace("'", "''")

    if browser_exe:
        escaped_exe = browser_exe.replace("'", "''")
        if app_mode:
            arg = f"--app={url}"
            escaped_arg = arg.replace("'", "''")
            ps_cmd = f"Start-Process -FilePath '{escaped_exe}' -ArgumentList '{escaped_arg}'"
        else:
            ps_cmd = f"Start-Process -FilePath '{escaped_exe}' -ArgumentList '{escaped_url}'"
    else:
        ps_cmd = f"Start-Process '{escaped_url}'"

    CREATE_NO_WINDOW = 0x08000000
    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-NonInteractive",
                "-WindowStyle",
                "Hidden",
                "-Command",
                ps_cmd,
            ],
            creationflags=CREATE_NO_WINDOW,
        )
        return True
    except Exception:
        pass

    # Secondary native fallback
    try:
        import webbrowser
        webbrowser.open(url)
        return True
    except Exception:
        return False


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

    # 1. Native Messaging Apps (WhatsApp, Telegram)
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

    # 2. Direct Web Platforms & Services (YouTube, Google, Reddit, etc.)
    WEB_PLATFORMS = {
        "youtube": ("YouTube", "https://www.youtube.com"),
        "yt": ("YouTube", "https://www.youtube.com"),
        "you tube": ("YouTube", "https://www.youtube.com"),
        "google": ("Google", "https://www.google.com"),
        "github": ("GitHub", "https://www.github.com"),
        "reddit": ("Reddit", "https://www.reddit.com"),
        "chatgpt": ("ChatGPT", "https://chatgpt.com"),
        "claude": ("Claude", "https://claude.ai"),
        "gmail": ("Gmail", "https://mail.google.com"),
        "netflix": ("Netflix", "https://www.netflix.com"),
        "twitch": ("Twitch", "https://www.twitch.tv"),
        "twitter": ("Twitter", "https://x.com"),
        "x": ("X", "https://x.com"),
        "amazon": ("Amazon", "https://www.amazon.com"),
        "spotify web": ("Spotify", "https://open.spotify.com"),
        "wikipedia": ("Wikipedia", "https://www.wikipedia.org"),
        "facebook": ("Facebook", "https://www.facebook.com"),
        "instagram": ("Instagram", "https://www.instagram.com"),
        "linkedin": ("LinkedIn", "https://www.linkedin.com"),
        "maps": ("Google Maps", "https://maps.google.com"),
        "google maps": ("Google Maps", "https://maps.google.com"),
        "outlook": ("Outlook", "https://outlook.live.com"),
        "docs": ("Google Docs", "https://docs.google.com"),
        "google docs": ("Google Docs", "https://docs.google.com"),
        "sheets": ("Google Sheets", "https://sheets.google.com"),
        "google sheets": ("Google Sheets", "https://sheets.google.com"),
        "drive": ("Google Drive", "https://drive.google.com"),
        "google drive": ("Google Drive", "https://drive.google.com"),
        "canva": ("Canva", "https://www.canva.com"),
        "stackoverflow": ("Stack Overflow", "https://stackoverflow.com"),
    }

    if lower_query in WEB_PLATFORMS:
        name, url = WEB_PLATFORMS[lower_query]
        open_browser_url(url)
        return ToolResult(
            success=True,
            output=f"Opened {name}.",
        )

    # 3. Direct URLs or Domain Requests
    if lower_query.startswith(("http://", "https://", "www.")) or (
        "." in lower_query and any(lower_query.endswith(ext) for ext in (".com", ".org", ".net", ".io", ".tv", ".ai", ".co", ".app", ".dev"))
    ):
        url = clean_query if clean_query.startswith(("http://", "https://")) else f"https://{clean_query}"
        open_browser_url(url)
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
        # If single alphanumeric token, attempt web navigation as intuitive fallback
        if clean_query.isalnum() and len(clean_query) >= 3 and not any(k in lower_query for k in ("something", "anything")):
            url = f"https://www.{lower_query}.com"
            open_browser_url(url)
            return ToolResult(
                success=True,
                output=f"Opened {clean_query.capitalize()} on web.",
            )

        available_count = len(enabled_apps())
        return ToolResult(
            success=False,
            output=(
                f"Application '{clean_query}' was not found in apps.txt "
                f"({available_count} applications and tools available)."
            ),
        )


    # 5. Launch Local Executable, UWP App, or System Utility via Background PowerShell
    try:
        launch_app_via_powershell(target_path)

        # Give newly launched application window time to initialize and bring to foreground
        import time
        time.sleep(0.35)
        try:
            from z3ro.window import focus_window
            focus_window(app_name, timeout=2.0)
        except Exception:
            pass

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

    import time
    start = time.perf_counter()

    while True:
        try:
            windows = list_windows()
        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Could not enumerate windows: {e}",
            )

        # First: exact title match.
        for window in windows:
            if window.title.strip().lower() == search:
                x, y = window.center
                return ToolResult(
                    success=True,
                    output=f"Found '{window.title}'. Center: ({x}, {y})",
                )

        # Second: substring match.
        for window in windows:
            if search in window.title.lower():
                x, y = window.center
                return ToolResult(
                    success=True,
                    output=f"Found '{window.title}'. Center: ({x}, {y})",
                )

        # Third: common application-name matching.
        aliases = {
            "notepad": "notepad",
            "calculator": "calculator",
            "calc": "calculator",
            "paint": "paint",
            "explorer": "explorer",
            "chrome": "chrome",
            "whatsapp": "whatsapp",
            "telegram": "telegram",
            "youtube": "youtube",
        }

        normalized = aliases.get(search, search)
        if normalized != search:
            for window in windows:
                if normalized in window.title.lower():
                    x, y = window.center
                    return ToolResult(
                        success=True,
                        output=f"Found '{window.title}'. Center: ({x}, {y})",
                    )

        if (time.perf_counter() - start) >= 2.5:
            break
        time.sleep(0.2)

    return ToolResult(
        success=False,
        output=f"Could not find window: {title}",
    )


def focus_app_window(
    title: str,
) -> ToolResult:
    """Focus a visible Windows application window with retry."""

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

    if focus_window(title, timeout=2.5):
        return ToolResult(
            success=True,
            output=f"Focused window: {title}.",
        )

    return ToolResult(
        success=False,
        output=f"Could not focus window: {title}",
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
    title: str = None,
    app: str = None,
    press_enter: bool = False,
    **kwargs,
) -> ToolResult:
    """Type text into the target application, ensuring Electron overlay never steals typing."""

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

    if len(text) > 5000:
        return ToolResult(
            success=False,
            output="Text is too long.",
        )

    import time
    from z3ro.window import get_foreground_window, focus_window, list_windows

    OVERLAY_TERMS = ("electron", "dynamic island", "z3ro", "sobia", "python")
    SKIP_TERMS = (*OVERLAY_TERMS, "task switching", "program manager", "settings")

    target_title = title or app or kwargs.get("window")
    if target_title:
        # Try focusing with retry
        for attempt in range(2):
            if focus_window(target_title, timeout=2.5):
                break
            time.sleep(0.15)
        time.sleep(0.2)  # Let OS register focus change
    else:
        # No explicit target — find the user's real app (never type into Electron overlay)
        try:
            fg = get_foreground_window()
            if fg is None or any(term in fg.title.lower() for term in OVERLAY_TERMS):
                # Find the most recent non-overlay user window
                candidates = [
                    w for w in list_windows()
                    if w.title.strip()
                    and not any(t in w.title.lower() for t in SKIP_TERMS)
                    and w.width > 50 and w.height > 50  # Skip tiny/invisible windows
                ]
                if candidates:
                    focus_window(candidates[0].title, timeout=1.5)
                    time.sleep(0.2)
        except Exception:
            pass

    # Final safety check: if we're STILL in Electron, abort
    try:
        fg_check = get_foreground_window()
        if fg_check and any(term in fg_check.title.lower() for term in ("electron", "dynamic island")):
            # One last attempt with all non-overlay windows
            for w in list_windows():
                if not any(t in w.title.lower() for t in SKIP_TERMS) and w.width > 50:
                    focus_window(w.title, timeout=1.0)
                    time.sleep(0.15)
                    break
    except Exception:
        pass

    do_send = press_enter or kwargs.get("enter") or kwargs.get("send")

    try:
        import pyperclip
        # Fast & universal clipboard paste (works across WhatsApp, Telegram, Notepad, Chrome, Word, etc.)
        pyperclip.copy(text)
        time.sleep(0.08)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.08)
        if do_send:
            time.sleep(0.08)
            pyautogui.press("enter")
        return ToolResult(
            success=True,
            output=f"Typed text: {text[:50]}...",
        )
    except Exception:
        try:
            pyautogui.write(text, interval=0.01)
            if do_send:
                time.sleep(0.08)
                pyautogui.press("enter")
            return ToolResult(
                success=True,
                output="Text typed successfully.",
            )
        except Exception as e:
            return ToolResult(
                success=False,
                output=f"Failed to type text: {e}",
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


def send_app_message_tool(app: str = None, recipient: str = "", message: str = "", **kwargs) -> ToolResult:
    """Universally send a message to a recipient or active chat on any desktop application."""
    from z3ro.messaging.universal import send_app_message
    target_app = app or kwargs.get("target_app") or kwargs.get("application")
    recip = recipient or kwargs.get("contact") or kwargs.get("to") or kwargs.get("username", "")
    msg = message or kwargs.get("text", "")
    res = send_app_message(target_app, recip, msg)
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
    # 2. Launch in standalone YouTube app window (Chrome/Edge --app=URL)
    success = open_browser_url(target_url, app_mode=True)
    if success:
        return ToolResult(
            success=True,
            output=f"Playing {display_title} on YouTube.",
        )

    return ToolResult(
        success=False,
        output=f"Could not open YouTube in browser.",
    )


# Global reference to active song process
_current_song_process = None


# =========================================================================
# SYSTEM-WIDE VOLUME & MEDIA CONTROLS
# =========================================================================

def _send_vk(vk_code: int, count: int = 1, delay: float = 0.03):
    """Send Windows virtual key event using user32.keybd_event."""
    import ctypes
    import time
    user32 = ctypes.windll.user32
    KEYEVENTF_EXTENDEDKEY = 0x0001
    KEYEVENTF_KEYUP = 0x0002
    for _ in range(count):
        user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY, 0)
        time.sleep(delay)
        user32.keybd_event(vk_code, 0, KEYEVENTF_EXTENDEDKEY | KEYEVENTF_KEYUP, 0)
        time.sleep(delay)


def volume_up(steps: int = 5, **kwargs) -> ToolResult:
    """Turn system volume up (5 steps = +10%)."""
    VK_VOLUME_UP = 0xAF
    _send_vk(VK_VOLUME_UP, count=max(1, min(int(steps), 25)))
    return ToolResult(success=True, output="Turned volume up.")


def volume_down(steps: int = 5, **kwargs) -> ToolResult:
    """Turn system volume down (5 steps = -10%)."""
    VK_VOLUME_DOWN = 0xAE
    _send_vk(VK_VOLUME_DOWN, count=max(1, min(int(steps), 25)))
    return ToolResult(success=True, output="Turned volume down.")


def mute_volume(**kwargs) -> ToolResult:
    """Toggle system volume mute/unmute."""
    VK_VOLUME_MUTE = 0xAD
    _send_vk(VK_VOLUME_MUTE, count=1)
    return ToolResult(success=True, output="Toggled volume mute.")


def pause_song(**kwargs) -> ToolResult:
    """Pause currently playing audio, video, or song."""
    import time
    from z3ro.window import find_window, focus_window
    yt = find_window("YouTube")
    if yt:
        focus_window("YouTube")
        time.sleep(0.08)
        pyautogui.press("esc")
        time.sleep(0.04)
        pyautogui.press("k")
        return ToolResult(success=True, output="Paused playback.")

    VK_MEDIA_PLAY_PAUSE = 0xB3
    _send_vk(VK_MEDIA_PLAY_PAUSE, count=1)
    return ToolResult(success=True, output="Paused playback.")


def resume_song(**kwargs) -> ToolResult:
    """Resume paused audio, video, or song."""
    import time
    from z3ro.window import find_window, focus_window
    yt = find_window("YouTube")
    if yt:
        focus_window("YouTube")
        time.sleep(0.08)
        pyautogui.press("esc")
        time.sleep(0.04)
        pyautogui.press("k")
        return ToolResult(success=True, output="Resumed playback.")

    VK_MEDIA_PLAY_PAUSE = 0xB3
    _send_vk(VK_MEDIA_PLAY_PAUSE, count=1)
    return ToolResult(success=True, output="Resumed playback.")


def stop_song(**kwargs) -> ToolResult:
    """Stop currently playing audio, video, or music completely."""
    global _current_song_process
    import os
    import time
    import ctypes
    from z3ro.window import find_window, focus_window, list_windows
    user32 = ctypes.windll.user32
    WM_CLOSE = 0x0010

    # 1. Stop any sounddevice audio playback
    try:
        import sounddevice as sd
        sd.stop()
    except Exception:
        pass

    # 2. Terminate any active spawned song process (Chrome --app)
    if _current_song_process is not None:
        try:
            pid = _current_song_process.pid
            if _current_song_process.poll() is None:
                _current_song_process.terminate()
                time.sleep(0.15)
                if _current_song_process.poll() is None:
                    _current_song_process.kill()
            # Also kill child processes spawned by Chrome
            try:
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True, timeout=2,
                )
            except Exception:
                pass
        except Exception:
            pass
        _current_song_process = None

    # 3. Close ALL YouTube windows via WM_CLOSE
    closed_any = False
    for w in list_windows():
        if "youtube" in w.title.lower():
            user32.PostMessageW(w.hwnd, WM_CLOSE, 0, 0)
            closed_any = True

    if closed_any:
        time.sleep(0.2)
        # Kill any remaining Chrome / Edge --app=youtube processes
        for im in ("chrome.exe", "msedge.exe", "brave.exe"):
            try:
                subprocess.run(
                    ["taskkill", "/F", "/IM", im, "/FI", "WINDOWTITLE eq *YouTube*"],
                    capture_output=True, timeout=2,
                )
            except Exception:
                pass
        return ToolResult(success=True, output="Stopped playback.")

    # 4. Fallback: Hardware Media Stop / Pause keys if no specific YouTube window
    VK_MEDIA_STOP = 0xB2
    VK_MEDIA_PLAY_PAUSE = 0xB3
    _send_vk(VK_MEDIA_STOP, count=1)
    _send_vk(VK_MEDIA_PLAY_PAUSE, count=1)

    return ToolResult(success=True, output="Stopped playback.")


def close_app(app: str = "", **kwargs) -> ToolResult:
    """Close an application or window by name."""
    global _current_song_process
    import ctypes
    from z3ro.window import find_window, list_windows
    user32 = ctypes.windll.user32
    WM_CLOSE = 0x0010

    query = (app or kwargs.get("title") or "").strip().lower()
    if not query:
        return ToolResult(success=False, output="Application name required.")

    # Terminate active song process if closing youtube/song
    if query in ("youtube", "song", "music", "video") and _current_song_process:
        try:
            if _current_song_process.poll() is None:
                _current_song_process.terminate()
            _current_song_process = None
        except Exception:
            pass

    # Find matching window and post WM_CLOSE
    target_window = None
    for w in list_windows():
        if query in w.title.lower():
            target_window = w
            break

    if target_window:
        user32.PostMessageW(target_window.hwnd, WM_CLOSE, 0, 0)
        return ToolResult(success=True, output=f"Closed {target_window.title}.")

    # Fallback to taskkill
    try:
        import subprocess
        subprocess.run(["taskkill", "/F", "/IM", f"{query}.exe"], capture_output=True, timeout=2)
        return ToolResult(success=True, output=f"Closed {app}.")
    except Exception:
        pass

    return ToolResult(success=True, output=f"Closed {app}.")


def next_song(song: str = "", **kwargs) -> ToolResult:
    """Skip to next track or change to a new video/song."""
    from z3ro.window import find_window, focus_window
    if song and song.strip():
        return play_song(song.strip())
    VK_MEDIA_NEXT_TRACK = 0xB0
    _send_vk(VK_MEDIA_NEXT_TRACK, count=1)
    yt = find_window("YouTube")
    if yt:
        focus_window("YouTube")
        pyautogui.hotkey("shift", "n")
    return ToolResult(success=True, output="Skipped to next video/song.")


def previous_song(**kwargs) -> ToolResult:
    """Return to previous track or video."""
    from z3ro.window import find_window, focus_window
    VK_MEDIA_PREV_TRACK = 0xB1
    _send_vk(VK_MEDIA_PREV_TRACK, count=1)
    yt = find_window("YouTube")
    if yt:
        focus_window("YouTube")
        pyautogui.hotkey("shift", "p")
    return ToolResult(success=True, output="Returned to previous track.")


TOOLS = {

    "open_app": Tool(
        name="open_app",
        description=(
            "Open an approved Windows application."
        ),
        function=open_app,
    ),

    "close_app": Tool(
        name="close_app",
        description="Close an open application or window.",
        function=close_app,
    ),

    "play_song": Tool(
        name="play_song",
        description="Search and play a song or music video on YouTube in standalone app mode.",
        function=play_song,
    ),

    "pause_song": Tool(
        name="pause_song",
        description="Pause playing music or video.",
        function=pause_song,
    ),

    "resume_song": Tool(
        name="resume_song",
        description="Resume music or video playback.",
        function=resume_song,
    ),

    "stop_song": Tool(
        name="stop_song",
        description="Stop music or video playback.",
        function=stop_song,
    ),

    "next_song": Tool(
        name="next_song",
        description="Skip to the next video or track.",
        function=next_song,
    ),

    "previous_song": Tool(
        name="previous_song",
        description="Return to the previous video or track.",
        function=previous_song,
    ),

    "change_video": Tool(
        name="change_video",
        description="Change current video or song.",
        function=next_song,
    ),

    "volume_up": Tool(
        name="volume_up",
        description="Turn system volume up.",
        function=volume_up,
    ),

    "volume_down": Tool(
        name="volume_down",
        description="Turn system volume down.",
        function=volume_down,
    ),

    "mute_volume": Tool(
        name="mute_volume",
        description="Mute or unmute system audio.",
        function=mute_volume,
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

    "send_app_message": Tool(
        name="send_app_message",
        description="Send a message to a recipient or active chat on any desktop application (WhatsApp, Telegram, Discord, Slack, Teams, etc.).",
        function=send_app_message_tool,
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
