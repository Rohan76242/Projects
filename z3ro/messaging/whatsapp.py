"""Z3RO / SOBIA — WhatsApp Messaging Integration.

Provides native Windows integration with WhatsApp Desktop (UWP) and Web fallback:
- Opening WhatsApp desktop application
- Direct messaging via whatsapp:// URI protocol
- Contact search and automated message sending via clipboard & keyboard automation
"""

import os
import re
import time
import urllib.parse
import subprocess
import webbrowser
from typing import Optional

import pyautogui
import pyperclip

from z3ro.logger import logger


WHATSAPP_AUMID = r"shell:AppsFolder\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"


def open_whatsapp() -> dict:
    """Launch the native WhatsApp desktop app on Windows and bring it to foreground."""
    try:
        try:
            os.startfile("whatsapp://")
            logger.info("Opened WhatsApp via whatsapp:// protocol.")
            time.sleep(0.5)
            return {"success": True, "output": "Opened WhatsApp."}
        except Exception:
            pass

        subprocess.Popen(["explorer.exe", WHATSAPP_AUMID])
        logger.info(f"Opened WhatsApp via UWP AppID: {WHATSAPP_AUMID}")
        time.sleep(0.5)
        return {"success": True, "output": "Opened WhatsApp."}
    except Exception as e:
        logger.error(f"Failed to open WhatsApp: {e}")
        # Fallback to web
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
    """Send a WhatsApp message to a phone number or contact name.

    Args:
        recipient: Phone number (e.g. '+1234567890') or contact name (e.g. 'John').
        message: The message text to send.
        auto_send: If True, automatically presses enter to send the message.
    """
    if not recipient or not recipient.strip():
        return {"success": False, "output": "Recipient name or phone number is required."}
    if not message or not message.strip():
        return {"success": False, "output": "Message text is required."}

    recipient_clean = recipient.strip()
    msg_clean = message.strip()
    phone = _clean_phone(recipient_clean)

    # 1. Phone number destination via native protocol
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
                # Press Enter to dispatch pre-filled message in WhatsApp
                pyautogui.press("enter")

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

    # 2. Contact Name destination via desktop UI automation
    try:
        from z3ro.window import focus_window

        # Launch or focus WhatsApp
        open_whatsapp()
        time.sleep(1.0)
        focus_window("WhatsApp", timeout=2.5)
        time.sleep(0.3)

        # Clear any prior dialog
        pyautogui.press("esc")
        time.sleep(0.15)

        # In WhatsApp Desktop:
        # Step A: Press Ctrl + N (New Chat) or Ctrl + F to activate search
        pyautogui.hotkey("ctrl", "n")
        time.sleep(0.4)

        # Step B: Paste contact name via clipboard for 100% accuracy (no dropped chars)
        pyperclip.copy(recipient_clean)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.6)

        # Step C: Select top search result (Down arrow then Enter)
        pyautogui.press("down")
        time.sleep(0.2)
        pyautogui.press("enter")
        time.sleep(0.6)

        # Step D: Paste message into chat box via clipboard
        pyperclip.copy(msg_clean)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(0.25)

        # Step E: Dispatch message
        if auto_send:
            pyautogui.press("enter")

        logger.info(f"Dispatched WhatsApp message to contact: {recipient_clean}")
        return {
            "success": True,
            "output": f"Sent WhatsApp message to {recipient_clean}.",
        }
    except Exception as e:
        logger.error(f"Desktop WhatsApp automation encountered error, falling back to Web: {e}")
        encoded_text = urllib.parse.quote(msg_clean)
        web_url = f"https://web.whatsapp.com/send?text={encoded_text}"
        webbrowser.open(web_url)
        return {
            "success": True,
            "output": f"Opened WhatsApp Web to message {recipient_clean}.",
        }
