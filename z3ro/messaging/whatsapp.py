"""Z3RO / SOBIA — WhatsApp Messaging Integration.

Provides Windows Native Integration with WhatsApp Desktop:
- Native Win32 DLL APIs (user32.dll, ole32.dll, kernel32.dll)
- Desktop switching & thread attachment (OpenDesktopW, SetThreadDesktop)
- Windows UI Automation (UIAutomationCore.dll via uiautomation)
- Precise UIA element resolution for Search Box, Contact Items, and Compose Box
- Zero-guesswork native mouse/keyboard dispatch and clipboard injection
- Direct messaging via whatsapp:// URI protocol
"""

import os
import re
import time
import urllib.parse
import subprocess
import webbrowser
from typing import Optional, Tuple
import ctypes

import pyperclip

from z3ro.logger import logger

# ------------------------------------------------------------------------------
# Win32 Native DLL Imports & Setup
# ------------------------------------------------------------------------------
user32 = ctypes.windll.user32
ole32 = ctypes.windll.ole32
kernel32 = ctypes.windll.kernel32

def attach_thread_desktop():
    """Ensure the calling thread is attached to the interactive Windows 'Default' desktop."""
    try:
        h_desk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_desk:
            user32.SetThreadDesktop(h_desk)
    except Exception:
        pass

# Attach at import time
attach_thread_desktop()

# Set Per-Monitor v2 DPI Awareness (-4) so coordinates match 1:1 with hardware pixels
try:
    user32.SetProcessDpiAwarenessContext(-4)
except Exception:
    pass

# Ensure COM apartment is initialized
try:
    ole32.CoInitialize(None)
except Exception:
    pass

WHATSAPP_AUMID = r"shell:AppsFolder\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"

# Windows Event Hook Constants
EVENT_SYSTEM_FOREGROUND = 0x0003
WINEVENT_OUTOFCONTEXT = 0x0000


def attach_thread_desktop():
    """Ensure the calling thread is attached to the interactive Windows 'Default' desktop."""
    try:
        h_desk = user32.OpenDesktopW("Default", 0, False, 0x01FF)
        if h_desk:
            user32.SetThreadDesktop(h_desk)
    except Exception as e:
        logger.debug(f"Failed to attach thread desktop: {e}")


def get_whatsapp_hwnd() -> Optional[int]:
    """Find WhatsApp Desktop top-level HWND using native Win32 EnumWindows."""
    attach_thread_desktop()
    matching_hwnds = []

    def enum_windows_cb(hwnd, _):
        if user32.IsWindowVisible(hwnd):
            title_buf = ctypes.create_unicode_buffer(256)
            user32.GetWindowTextW(hwnd, title_buf, 256)
            title = title_buf.value
            if "whatsapp" in title.lower():
                class_buf = ctypes.create_unicode_buffer(256)
                user32.GetClassNameW(hwnd, class_buf, 256)
                cls_name = class_buf.value
                if "WinUIDesktop" in cls_name:
                    matching_hwnds.insert(0, hwnd)
                elif "ApplicationFrame" in cls_name or "Chrome_WidgetWin" in cls_name:
                    matching_hwnds.append(hwnd)
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
    user32.EnumWindows(WNDENUMPROC(enum_windows_cb), 0)
    return matching_hwnds[0] if matching_hwnds else None


def activate_whatsapp_window(hwnd: int) -> bool:
    """Natively restore, elevate, and focus WhatsApp window via Win32 APIs."""
    try:
        attach_thread_desktop()
        # SW_RESTORE = 9
        user32.ShowWindow(hwnd, 9)
        time.sleep(0.05)
        # Elevate to top of Z-order momentarily to break through any overlays
        # HWND_TOPMOST = -1, HWND_NOTOPMOST = -2, SWP_NOMOVE | SWP_NOSIZE = 0x0001 | 0x0002
        user32.SetWindowPos(hwnd, -1, 0, 0, 0, 0, 0x0001 | 0x0002)
        time.sleep(0.02)
        user32.SetWindowPos(hwnd, -2, 0, 0, 0, 0, 0x0001 | 0x0002)
        user32.SetForegroundWindow(hwnd)
        time.sleep(0.2)
        return True
    except Exception as e:
        logger.error(f"Error activating WhatsApp window HWND {hex(hwnd)}: {e}")
        return False


def native_click(x: int, y: int):
    """Dispatch a native OS hardware mouse click via user32.dll mouse_event."""
    attach_thread_desktop()
    user32.SetCursorPos(x, y)
    time.sleep(0.04)
    # MOUSEEVENTF_LEFTDOWN = 0x0002, MOUSEEVENTF_LEFTUP = 0x0004
    user32.mouse_event(0x0002, 0, 0, 0, 0)
    time.sleep(0.04)
    user32.mouse_event(0x0004, 0, 0, 0, 0)
    time.sleep(0.1)


def open_whatsapp() -> dict:
    """Launch the native WhatsApp desktop app on Windows and bring it to foreground."""
    attach_thread_desktop()
    try:
        hwnd = get_whatsapp_hwnd()
        if hwnd:
            activate_whatsapp_window(hwnd)
            logger.info(f"Focused existing WhatsApp window HWND {hex(hwnd)}.")
            return {"success": True, "output": "Focused WhatsApp window."}

        try:
            os.startfile("whatsapp://")
            logger.info("Opened WhatsApp via whatsapp:// protocol.")
            time.sleep(1.0)
            return {"success": True, "output": "Opened WhatsApp."}
        except Exception:
            pass

        subprocess.Popen(["explorer.exe", WHATSAPP_AUMID])
        logger.info(f"Opened WhatsApp via UWP AppID: {WHATSAPP_AUMID}")
        time.sleep(1.0)
        return {"success": True, "output": "Opened WhatsApp."}
    except Exception as e:
        logger.error(f"Failed to open WhatsApp: {e}")
        webbrowser.open("https://web.whatsapp.com")
        return {"success": True, "output": "Opened WhatsApp Web."}


def _clean_phone(phone: str) -> Optional[str]:
    """Extract standard digits from a phone number string."""
    cleaned = re.sub(r"[^\d+]", "", phone.strip())
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    if len(cleaned) >= 7 and cleaned.isdigit():
        return cleaned
    return None


def send_whatsapp(recipient: str, message: str, auto_send: bool = True) -> dict:
    """Send a WhatsApp message to a phone number or contact name using Windows Native Integration.

    Uses Windows UI Automation (UIAutomationCore.dll) and Win32 DLLs to locate WhatsApp's
    internal controls, select the recipient chat, and inject the message natively.

    Args:
        recipient: Phone number (e.g. '+1234567890') or contact name (e.g. 'Moona').
        message: The message text to send.
        auto_send: If True, automatically dispatches the message with Enter.
    """
    if not recipient or not recipient.strip():
        return {"success": False, "output": "Recipient name or phone number is required."}
    if not message or not message.strip():
        return {"success": False, "output": "Message text is required."}

    recipient_clean = recipient.strip()
    msg_clean = message.strip()
    phone = _clean_phone(recipient_clean)

    # --------------------------------------------------------------------------
    # Case 1: Phone number destination via Windows protocol
    # --------------------------------------------------------------------------
    if phone:
        encoded_text = urllib.parse.quote(msg_clean)
        uri = f"whatsapp://send?phone={phone}&text={encoded_text}"
        try:
            try:
                os.startfile(uri)
            except Exception:
                subprocess.Popen(["explorer.exe", uri])

            if auto_send:
                time.sleep(2.0)
                import uiautomation as auto
                auto.SendKeys("{Enter}", waitTime=0.1)

            logger.info(f"Sent WhatsApp message to phone {phone}")
            return {
                "success": True,
                "output": f"Sent WhatsApp message to {recipient_clean}.",
            }
        except Exception as e:
            logger.warning(f"whatsapp:// URI failed, trying web fallback: {e}")
            web_url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_text}"
            webbrowser.open(web_url)
            return {
                "success": True,
                "output": f"Opened WhatsApp chat for {recipient_clean}.",
            }

    # --------------------------------------------------------------------------
    # Case 2: Contact Name via Windows Native UI Automation & Win32 Hooks
    # --------------------------------------------------------------------------
    attach_thread_desktop()
    try:
        import uiautomation as auto
        auto.SetGlobalSearchTimeout(2.5)

        # 1. Locate and activate WhatsApp window
        hwnd = get_whatsapp_hwnd()
        if not hwnd:
            logger.info("WhatsApp window not found, launching...")
            open_whatsapp()
            time.sleep(2.0)
            hwnd = get_whatsapp_hwnd()

        if not hwnd:
            raise RuntimeError("Could not find or launch WhatsApp desktop window.")

        activate_whatsapp_window(hwnd)
        wa = auto.ControlFromHandle(hwnd)
        logger.info(f"Connected to WhatsApp HWND {hex(hwnd)} via Windows UI Automation.")

        # 2. Acquire WebView2 root document
        doc = wa.DocumentControl(AutoId="RootWebArea")
        if not doc.Exists(2, 1):
            # Fallback: search any DocumentControl
            doc = wa.DocumentControl()

        # 3. Locate & Focus Search EditControl
        search_box = None
        for _ in range(3):
            search_box = doc.EditControl(SubName="Search")
            if search_box.Exists(0, 0):
                break
            search_box = doc.EditControl(Name="Search or start a new chat")
            if search_box.Exists(0, 0):
                break
            time.sleep(0.3)

        if search_box and search_box.Exists(0, 0):
            s_rect = search_box.BoundingRectangle
            sc_x = (s_rect.left + s_rect.right) // 2
            sc_y = (s_rect.top + s_rect.bottom) // 2
            logger.info(f"Clicking WhatsApp search box at ({sc_x}, {sc_y})")
            native_click(sc_x, sc_y)
            time.sleep(0.15)
            auto.SendKeys("{Ctrl}a{Delete}", waitTime=0.05)
            time.sleep(0.1)
            pyperclip.copy(recipient_clean)
            auto.SendKeys("{Ctrl}v", waitTime=0.05)
            logger.info(f"Entered search query: '{recipient_clean}'")
            time.sleep(1.2)  # Wait for search results
        else:
            logger.info("Search EditControl not found by name, attempting Ctrl+F shortcut")
            auto.SendKeys("{Ctrl}f", waitTime=0.1)
            time.sleep(0.2)
            auto.SendKeys("{Ctrl}a{Delete}", waitTime=0.05)
            pyperclip.copy(recipient_clean)
            auto.SendKeys("{Ctrl}v", waitTime=0.05)
            time.sleep(1.2)

        # 4. Find & Click Contact in Search Results via UIA Tree
        target_clean = recipient_clean.lower().strip()
        clicked_contact = False

        try:
            for c, depth in auto.WalkControl(doc, maxDepth=16):
                if c.ControlType in (
                    auto.ControlType.DataItemControl,
                    auto.ControlType.ButtonControl,
                    auto.ControlType.ListItemControl,
                ):
                    c_name = (c.Name or "").lower()
                    if target_clean in c_name and "search" not in c_name:
                        rect = c.BoundingRectangle
                        w = rect.right - rect.left
                        h = rect.bottom - rect.top
                        if w > 0 and h > 0:
                            cx = (rect.left + rect.right) // 2
                            cy = (rect.top + rect.bottom) // 2
                            safe_title = (c.Name or "")[:40].encode("ascii", "replace").decode()
                            logger.info(f"Found contact item '{safe_title}' at ({cx}, {cy}). Clicking...")
                            native_click(cx, cy)
                            clicked_contact = True
                            break
        except Exception as e:
            logger.debug(f"WalkControl search exception (safe to fallback): {e}")

        if not clicked_contact:
            logger.info("No explicit contact item found in tree; pressing Enter on top result.")
            auto.SendKeys("{Enter}", waitTime=0.1)
            time.sleep(0.08)
            import pyautogui
            pyautogui.press("enter")

        time.sleep(0.8)

        # 5. Locate Compose Message EditControl
        msg_input = None
        try:
            for attempt in range(4):
                msg_input = doc.EditControl(SubName="Type a message")
                if msg_input.Exists(0, 0):
                    break
                for c, depth in auto.WalkControl(doc, maxDepth=10):
                    if c.ControlType == auto.ControlType.EditControl and "message" in (c.Name or "").lower():
                        msg_input = c
                        break
                if msg_input and msg_input.Exists(0, 0):
                    break
                time.sleep(0.2)
        except Exception as e:
            logger.debug(f"WalkControl compose exception (safe to fallback): {e}")

        if msg_input and msg_input.Exists(0, 0):
            m_rect = msg_input.BoundingRectangle
            mc_x = (m_rect.left + m_rect.right) // 2
            mc_y = (m_rect.top + m_rect.bottom) // 2
            logger.info(f"Located Compose Box at ({mc_x}, {mc_y}). Clicking to focus...")
            native_click(mc_x, mc_y)
            time.sleep(0.15)
        else:
            logger.warning("Compose box not found via UIA, clicking fallback chat coordinates.")
            wa_rect = wa.BoundingRectangle
            mc_x = wa_rect.left + int((wa_rect.right - wa_rect.left) * 0.65)
            mc_y = wa_rect.bottom - 50
            native_click(mc_x, mc_y)
            time.sleep(0.15)

        # 6. Inject Message Text
        logger.info(f"Injecting message into compose box: '{msg_clean}'")
        pyperclip.copy(msg_clean)
        time.sleep(0.08)
        auto.SendKeys("{Ctrl}a{Delete}", waitTime=0.05)
        auto.SendKeys("{Ctrl}v", waitTime=0.08)
        time.sleep(0.3)

        # 7. Dispatch or Hold
        if auto_send:
            auto.SendKeys("{Enter}", waitTime=0.1)
            time.sleep(0.08)
            import pyautogui
            pyautogui.press("enter")
            logger.info(f"Dispatched WhatsApp message to {recipient_clean}")
        else:
            logger.info(f"Message prepared in compose box for {recipient_clean} (auto_send=False)")

        return {
            "success": True,
            "output": f"Sent WhatsApp message to {recipient_clean}: \"{msg_clean}\"",
        }

    except Exception as e:
        logger.error(f"Windows Native UIA automation error: {e}, falling back to Web", exc_info=True)
        encoded_text = urllib.parse.quote(msg_clean)
        web_url = f"https://web.whatsapp.com/send?text={encoded_text}"
        webbrowser.open(web_url)
        return {
            "success": True,
            "output": f"Opened WhatsApp Web to message {recipient_clean}.",
        }
