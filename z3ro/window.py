import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import time


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


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
    try:
        hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if hdesk:
            user32.SetThreadDesktop(hdesk)
    except Exception:
        pass

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
    timeout: float = 0.0,
) -> WindowInfo | None:
    """Find the first visible window matching a title, with optional polling timeout."""

    if not isinstance(title, str):
        return None

    search = title.lower().strip()

    if not search:
        return None

    start = time.perf_counter()
    while True:
        for window in list_windows():
            if search in window.title.lower():
                return window

        if timeout <= 0.0 or (time.perf_counter() - start) >= timeout:
            break
        time.sleep(0.15)

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
    timeout: float = 1.5,
) -> bool:
    """Bring a matching window to the foreground reliably using Win32 foreground lock bypass."""

    window = find_window(title, timeout=timeout)

    if window is None:
        return False

    SW_RESTORE = 9
    SW_SHOW = 5

    # If minimized, restore it
    if user32.IsIconic(window.hwnd):
        user32.ShowWindow(window.hwnd, SW_RESTORE)
    else:
        user32.ShowWindow(window.hwnd, SW_SHOW)

    time.sleep(0.08)

    # Force foreground window even if OS blocks background processes
    cur_thread = kernel32.GetCurrentThreadId()
    fg_hwnd = user32.GetForegroundWindow()
    fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0

    if fg_thread and cur_thread != fg_thread:
        user32.AttachThreadInput(cur_thread, fg_thread, True)
        user32.SetForegroundWindow(window.hwnd)
        user32.SetFocus(window.hwnd)
        user32.AttachThreadInput(cur_thread, fg_thread, False)
    else:
        user32.SetForegroundWindow(window.hwnd)
        user32.SetFocus(window.hwnd)

    time.sleep(0.12)
    return is_window_focused(title) or user32.GetForegroundWindow() == window.hwnd


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