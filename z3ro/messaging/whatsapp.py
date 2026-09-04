"""Z3RO / SOBIA — WhatsApp Messaging Integration.

Provides native Windows integration with WhatsApp Desktop (UWP) and Web fallback:
- Opening WhatsApp desktop application
- Direct messaging via whatsapp:// URI protocol
- Contact search and automated message sending via keyboard automation
"""

import os
import re
import time
import urllib.parse
import subprocess
import webbrowser
from typing import Optional

import pyautogui

from z3ro.logger import logger


WHATSAPP_AUMID = r"shell:AppsFolder\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"


def open_whatsapp() -> dict:
    """Launch the native WhatsApp desktop app on Windows."""
    try:
        try:
            os.startfile("whatsapp://")
            logger.info("Opened WhatsApp via whatsapp:// protocol.")
            return {"success": True, "output": "Opened WhatsApp."}
        except Exception:
            pass

        subprocess.Popen(["explorer.exe", WHATSAPP_AUMID])
        logger.info(f"Opened WhatsApp via UWP AppID: {WHATSAPP_AUMID}")
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

            logger.info(f"Sent WhatsApp message to {phone}")
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
        open_whatsapp()
        time.sleep(1.8)

        # Focus WhatsApp search bar
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.3)
        pyautogui.write(recipient_clean, interval=0.04)
        time.sleep(0.8)
        pyautogui.press("enter")
        time.sleep(0.8)

        # Type message in the chat compose area
        pyautogui.write(msg_clean, interval=0.03)

        if auto_send:
            time.sleep(0.3)
            pyautogui.press("enter")

        logger.info(f"Dispatched WhatsApp message to contact: {recipient_clean}")
        return {
            "success": True,
            "output": f"Sent WhatsApp message to {recipient_clean}.",
        }
    except Exception as e:
        logger.error(f"Failed to automate WhatsApp send: {e}")
        return {
            "success": False,
            "output": f"Failed to send WhatsApp message to {recipient_clean}: {e}",
        }
