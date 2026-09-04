import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import time


user32 = ctypes.windll.user32


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    left: int = 0
    top: int = 0
    right: int = 0
    bottom: int = 0

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    @property
    def center(self) -> tuple[int, int]:
        return (
            self.left + self.width // 2,
            self.top + self.height // 2,
        )


def get_window_rect(hwnd: int):
    """Get the screen rectangle of a window."""

    rect = wintypes.RECT()

    if not user32.GetWindowRect(
        hwnd,
        ctypes.byref(rect),
    ):
        return None

    return rect


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

        buffer = ctypes.create_unicode_buffer(
            length + 1
        )

        user32.GetWindowTextW(
            hwnd,
            buffer,
            length + 1,
        )

        title = buffer.value.strip()

        if not title:
            return True

        rect = get_window_rect(hwnd)

        if rect is None:
            return True

        windows.append(
            WindowInfo(
                hwnd=hwnd,
                title=title,
                left=rect.left,
                top=rect.top,
                right=rect.right,
                bottom=rect.bottom,
            )
        )

        return True

    user32.EnumWindows(
        EnumWindowsProc(callback),
        0,
    )

    return windows


def find_window(
    title: str,
) -> WindowInfo | None:
    """Find the first visible window matching a title."""

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
    """Return the currently focused window."""

    hwnd = user32.GetForegroundWindow()

    if not hwnd:
        return None

    length = user32.GetWindowTextLengthW(
        hwnd
    )

    if length == 0:
        return None

    buffer = ctypes.create_unicode_buffer(
        length + 1
    )

    user32.GetWindowTextW(
        hwnd,
        buffer,
        length + 1,
    )

    title = buffer.value.strip()

    if not title:
        return None

    rect = get_window_rect(hwnd)

    if rect is None:
        return None

    return WindowInfo(
        hwnd=hwnd,
        title=title,
        left=rect.left,
        top=rect.top,
        right=rect.right,
        bottom=rect.bottom,
    )


def is_window_visible(
    title: str,
) -> bool:

    return find_window(title) is not None


def is_window_focused(
    title: str,
) -> bool:

    target = find_window(title)
    foreground = get_foreground_window()

    if target is None:
        return False

    if foreground is None:
        return False

    return target.hwnd == foreground.hwnd


def focus_window(
    title: str,
) -> bool:
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


def get_window_center(
    title: str,
) -> tuple[int, int] | None:
    """Return the REAL screen center of a window."""

    window = find_window(title)

    if window is None:
        return None

    return window.center


if __name__ == "__main__":

    print("================================")
    print("      Z3RO WINDOW MANAGER")
    print("================================")
    print()

    windows = list_windows()

    print(
        f"Found {len(windows)} visible windows:"
    )
    print()

    for window in windows:

        print(
            f"[{window.hwnd}] "
            f"{window.title}"
        )

        print(
            f"    Position: "
            f"({window.left}, {window.top})"
        )

        print(
            f"    Size: "
            f"{window.width}x{window.height}"
        )

        print(
            f"    Center: "
            f"{window.center}"
        )

    print()

    target = input(
        "Window to inspect: "
    ).strip()

    window = find_window(target)

    if window is None:

        print(
            f"Window not found: {target}"
        )

        raise SystemExit(1)

    print()
    print(
        f"Window: {window.title}"
    )

    print(
        f"Position: "
        f"({window.left}, {window.top})"
    )

    print(
        f"Size: "
        f"{window.width}x{window.height}"
    )

    print(
        f"REAL CENTER: "
        f"{window.center}"
    )