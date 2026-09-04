"""Z3RO / SOBIA — Telegram Messaging Integration.

Provides native Windows integration with Telegram Desktop:
- Opening Telegram Desktop application
- Direct messaging via tg:// URI protocol and Telegram links
- Direct sending via Telegram Bot API if configured
- Automated contact search and message dispatch via keyboard automation
"""

import os
import json
import time
import urllib.parse
import urllib.request
import subprocess
import webbrowser
from typing import Optional

import pyautogui

from z3ro.config import config
from z3ro.logger import logger


TELEGRAM_AUMID = r"shell:AppsFolder\TelegramMessengerLLP.TelegramDesktop_t4vj0pshhgkwm!Telegram.TelegramDesktop"


def open_telegram() -> dict:
    """Launch the native Telegram desktop app on Windows."""
    try:
        try:
            os.startfile("tg://")
            logger.info("Opened Telegram via tg:// protocol.")
            return {"success": True, "output": "Opened Telegram."}
        except Exception:
            pass

        subprocess.Popen(["explorer.exe", TELEGRAM_AUMID])
        logger.info(f"Opened Telegram via UWP AppID: {TELEGRAM_AUMID}")
        return {"success": True, "output": "Opened Telegram."}
    except Exception as e:
        logger.error(f"Failed to open Telegram: {e}")
        webbrowser.open("https://web.telegram.org")
        return {"success": True, "output": "Opened Telegram Web."}


def _send_via_bot_api(chat_id: str, message: str) -> Optional[dict]:
    """Send a message using Telegram Bot API if credentials are configured."""
    bot_token = getattr(config, "TELEGRAM_BOT_TOKEN", None)
    if not bot_token:
        return None

    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({"chat_id": chat_id, "text": message}).encode("utf-8")
    try:
        req = urllib.request.Request(
            api_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("ok"):
                return {"success": True, "output": f"Sent Telegram message to {chat_id} via Bot API."}
    except Exception as e:
        logger.warning(f"Telegram Bot API send failed: {e}")
    return None


def send_telegram(recipient: str, message: str, auto_send: bool = True) -> dict:
    """Send a Telegram message to a username, chat ID, or contact name.

    Args:
        recipient: Telegram @username, chat ID, or contact name.
        message: The message text to send.
        auto_send: If True, automatically dispatches the message.
    """
    if not recipient or not recipient.strip():
        return {"success": False, "output": "Recipient username or name is required."}
    if not message or not message.strip():
        return {"success": False, "output": "Message text is required."}

    recipient_clean = recipient.strip()
    msg_clean = message.strip()

    # 1. Try Bot API if configured and recipient looks like a chat ID
    if recipient_clean.isdigit() or (recipient_clean.startswith("-") and recipient_clean[1:].isdigit()):
        bot_res = _send_via_bot_api(recipient_clean, msg_clean)
        if bot_res:
            return bot_res

    # 2. If recipient is a @username or direct username
    if recipient_clean.startswith("@") or (" " not in recipient_clean and len(recipient_clean) > 3):
        clean_user = recipient_clean.lstrip("@")
        encoded_text = urllib.parse.quote(msg_clean)
        uri = f"tg://msg?to={clean_user}&text={encoded_text}"
        try:
            try:
                os.startfile(uri)
            except Exception:
                subprocess.Popen(["explorer.exe", uri])

            if auto_send:
                time.sleep(2.0)
                pyautogui.press("enter")

            logger.info(f"Dispatched Telegram message to @{clean_user}")
            return {
                "success": True,
                "output": f"Sent Telegram message to {recipient_clean}.",
            }
        except Exception as e:
            logger.warning(f"tg:// protocol failed, opening t.me link: {e}")
            webbrowser.open(f"https://t.me/{clean_user}")
            return {
                "success": True,
                "output": f"Opened Telegram chat for {recipient_clean}.",
            }

    # 3. Contact name via desktop UI automation
    try:
        open_telegram()
        time.sleep(1.8)

        # Focus search bar
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.3)
        pyautogui.write(recipient_clean, interval=0.04)
        time.sleep(0.8)
        pyautogui.press("enter")
        time.sleep(0.8)

        # Type message
        pyautogui.write(msg_clean, interval=0.03)

        if auto_send:
            time.sleep(0.3)
            pyautogui.press("enter")

        logger.info(f"Dispatched Telegram message to contact: {recipient_clean}")
        return {
            "success": True,
            "output": f"Sent Telegram message to {recipient_clean}.",
        }
    except Exception as e:
        logger.error(f"Failed to automate Telegram send: {e}")
        return {
            "success": False,
            "output": f"Failed to send Telegram message to {recipient_clean}: {e}",
        }
