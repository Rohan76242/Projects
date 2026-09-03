import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import time


user32 = ctypes.windll.user32


@dataclass
class WindowInfo:
    hwnd: int
    title: str


def list_windows() -> list[WindowInfo]:
    """Return visible Windows with non-empty titles."""

    windows = []

    EnumWindowsProc = ctypes.WINFUNCTYPE(
        wintypes.BOOL,
        wintypes.HWND,
        wintypes.LPARAM,
    )

    def callback(hwnd, _):

        if not user32.IsWindowVisible(hwnd):
            return True

        length = user32.GetWindowTextLengthW(hwnd)

        if length == 0:
            return True

        buffer = ctypes.create_unicode_buffer(length + 1)

        user32.GetWindowTextW(
            hwnd,
            buffer,
            length + 1,
        )

        title = buffer.value.strip()

        if title:
            windows.append(
                WindowInfo(
                    hwnd=hwnd,
                    title=title,
                )
            )

        return True

    user32.EnumWindows(
        EnumWindowsProc(callback),
        0,
    )

    return windows


def find_window(title: str) -> WindowInfo | None:
    """Find the first visible window containing the supplied title."""

    if not isinstance(title, str):
        return None

    search = title.lower().strip()

    if not search:
        return None

    for window in list_windows():

        if search in window.title.lower():
            return window

    return None


def get_foreground_window() -> WindowInfo | None:
    """Return the currently focused foreground window."""

    hwnd = user32.GetForegroundWindow()

    if not hwnd:
        return None

    length = user32.GetWindowTextLengthW(hwnd)

    if length == 0:
        return None

    buffer = ctypes.create_unicode_buffer(length + 1)

    user32.GetWindowTextW(
        hwnd,
        buffer,
        length + 1,
    )

    title = buffer.value.strip()

    if not title:
        return None

    return WindowInfo(
        hwnd=hwnd,
        title=title,
    )


def is_window_visible(title: str) -> bool:
    """Check whether a matching visible window exists."""

    return find_window(title) is not None


def is_window_focused(title: str) -> bool:
    """Check whether a matching window is currently focused."""

    target = find_window(title)
    foreground = get_foreground_window()

    if target is None or foreground is None:
        return False

    return target.hwnd == foreground.hwnd


def focus_window(title: str) -> bool:
    """Bring a matching window to the foreground."""

    window = find_window(title)

    if window is None:
        return False

    user32.ShowWindow(
        window.hwnd,
        5,
    )

    time.sleep(0.2)

    user32.SetForegroundWindow(
        window.hwnd,
    )

    time.sleep(0.2)

    return is_window_focused(title)


if __name__ == "__main__":

    print("================================")
    print("      Z3RO WINDOW MANAGER")
    print("================================")
    print()

    windows = list_windows()

    print(f"Found {len(windows)} visible windows:")
    print()

    for window in windows:
        print(f"[{window.hwnd}] {window.title}")

    print()

    target = input("Window to focus: ").strip()

    if focus_window(target):

        print(f"Focused: {target}")

        if is_window_focused(target):
            print("Verification: SUCCESS")

        else:
            print("Verification: FAILED")

    else:

        print(f"Window not found: {target}")