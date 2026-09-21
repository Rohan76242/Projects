import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import time


user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Enable Per-Monitor V2 DPI Awareness so Win32 GetWindowRect matches pyautogui's physical pixel space
try:
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        pass



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


def attach_thread_desktop():
    """Ensure the calling thread is attached to the interactive Windows 'Default' desktop."""
    try:
        hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if hdesk:
            user32.SetThreadDesktop(hdesk)
    except Exception:
        pass


def list_windows() -> list[WindowInfo]:
    """Return visible Windows with non-empty titles."""
    attach_thread_desktop()
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

        # Skip zero-sized or collapsed windows
        if (rect.right - rect.left) <= 0 or (rect.bottom - rect.top) <= 0:
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

    proc = EnumWindowsProc(callback)
    hdesk = None
    try:
        hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if hdesk:
            user32.EnumDesktopWindows(hdesk, proc, 0)
        else:
            user32.EnumWindows(proc, 0)
    except Exception:
        user32.EnumWindows(proc, 0)
    finally:
        if hdesk:
            try:
                user32.CloseDesktop(hdesk)
            except Exception:
                pass

    return windows


def find_window(
    title: str,
    timeout: float = 0.0,
) -> WindowInfo | None:
    """Find the first visible window matching a title, with optional polling timeout."""
    attach_thread_desktop()

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
    attach_thread_desktop()

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

    try:
        hdesk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if hdesk:
            user32.SetThreadDesktop(hdesk)
    except Exception:
        pass

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

    # Windows foreground lock bypass:
    # 1. Synthesize Alt key tap so Windows recognizes active user event
    VK_MENU = 0x12  # Alt key
    KEYEVENTF_KEYUP = 0x0002
    user32.keybd_event(VK_MENU, 0, 0, 0)
    user32.keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, 0)

    # 2. Elevate window to top of Z-order (above even topmost overlays)
    HWND_TOPMOST = -1
    HWND_NOTOPMOST = -2
    SWP_NOSIZE = 0x0001
    SWP_NOMOVE = 0x0002
    SWP_SHOWWINDOW = 0x0040
    user32.SetWindowPos(window.hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)
    user32.SetWindowPos(window.hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW)

    # 3. Attach input thread and set foreground
    cur_thread = kernel32.GetCurrentThreadId()
    fg_hwnd = user32.GetForegroundWindow()
    fg_thread = user32.GetWindowThreadProcessId(fg_hwnd, None) if fg_hwnd else 0
    target_thread = user32.GetWindowThreadProcessId(window.hwnd, None)

    if fg_thread and cur_thread != fg_thread:
        user32.AttachThreadInput(cur_thread, fg_thread, True)
    if target_thread and cur_thread != target_thread:
        user32.AttachThreadInput(cur_thread, target_thread, True)

    user32.SetForegroundWindow(window.hwnd)
    user32.BringWindowToTop(window.hwnd)
    user32.SetFocus(window.hwnd)

    if fg_thread and cur_thread != fg_thread:
        user32.AttachThreadInput(cur_thread, fg_thread, False)
    if target_thread and cur_thread != target_thread:
        user32.AttachThreadInput(cur_thread, target_thread, False)

    time.sleep(0.15)
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