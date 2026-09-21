"""Z3RO / SOBIA — Universal Multi-App Messaging Hub.

Handles messaging dispatch across all desktop applications:
- WhatsApp Desktop (Native Win32 + UIAutomation)
- Telegram Desktop (Desktop quick-switcher + protocol)
- Discord (Quick switcher Ctrl+K + DM/channel dispatch)
- Slack (Quick switcher Ctrl+K + channel/user dispatch)
- Microsoft Teams (Chat switcher + dispatch)
- Skype (Search + dispatch)
- Generic Chat Apps (Active chat window injection)
- Active Window (Direct paste & send into whatever app the user has focused)
"""

import re
import time
import urllib.parse
from typing import Optional, Dict, Any
import pyautogui
pyautogui.FAILSAFE = False
import pyperclip

from z3ro.logger import logger
from z3ro.window import find_window, focus_window, list_windows, get_foreground_window
from z3ro.tools.system import open_app, type_text


KNOWN_APPS = {
    "whatsapp": ("whatsapp", "wa"),
    "telegram": ("telegram", "tg"),
    "discord": ("discord",),
    "slack": ("slack",),
    "teams": ("teams", "microsoft teams", "ms teams"),
    "skype": ("skype",),
    "messenger": ("messenger", "facebook messenger"),
    "instagram": ("instagram", "insta", "ig"),
    "signal": ("signal",),
}


def resolve_app(app_str: Optional[str]) -> str:
    """Normalize app string to standard name, defaulting to whatsapp."""
    if not app_str:
        return "whatsapp"
    clean = app_str.lower().strip()
    for std_name, aliases in KNOWN_APPS.items():
        if clean == std_name or clean in aliases:
            return std_name
    return clean


def extract_message_intent(user_input: str) -> Optional[Dict[str, Any]]:
    """Extract (app, recipient, message) from any natural message command."""
    text = user_input.strip()

    # 1. Normalize speech recognition artifacts & wake words
    text = re.sub(r"^(?:(?:hey|ok|okay|hi|hello)[\s,]+)?(?:zero|z3ro|sobia|assistant)\b[\s,:\-]*", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"^(?:(?:can|could|would)\s+you\s+(?:please\s+)?|please\s+|kindly\s+)", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"[\s,]+(?:for\s+me|please|right\s+now|now|quickly|asap)[\.?!]*$", "", text, flags=re.IGNORECASE).strip()

    text = re.sub(r"\bwhats\s*aap\b", "whatsapp", text, flags=re.IGNORECASE)
    text = re.sub(r"\bwhats\s*app\b", "whatsapp", text, flags=re.IGNORECASE)
    text = re.sub(r"\bwhat's\s*app\b", "whatsapp", text, flags=re.IGNORECASE)
    text = re.sub(r"\btxt\b", "text", text, flags=re.IGNORECASE)
    text = re.sub(r"\bmsz\b", "message", text, flags=re.IGNORECASE)
    text = re.sub(r"\bmsg\b", "message", text, flags=re.IGNORECASE)
    text = re.sub(r"\btele\s*gram\b", "telegram", text, flags=re.IGNORECASE)

    # Helper to strip message fillers
    def clean_msg(m: str) -> str:
        s = m.strip()
        for filler in ("saying ", "that ", "with ", "message is ", "say ", "text is "):
            if s.lower().startswith(filler):
                s = s[len(filler):].strip()
        return s

    # 2. Reply patterns (e.g. "reply hello", "reply that I am busy")
    m_reply = re.match(
        r"^(?:(?:yes|yeah|sure|ok|okay)[\s,]*)?(?:reply|respond)\s*(?:back|to\s+(?:him|her|them))?\s*(?:saying|that|with)?[\s,:\-]*(.+)$",
        text,
        re.IGNORECASE,
    )
    if m_reply:
        msg = clean_msg(m_reply.group(1))
        if msg:
            return {"type": "reply", "app": None, "recipient": None, "message": msg}

    # 3. Explicit type-and-send commands
    m_type_send = re.match(r"^type\s+and\s+send\s+(.+)$", text, re.IGNORECASE)
    if m_type_send:
        return {"type": "send_active", "app": None, "recipient": None, "message": clean_msg(m_type_send.group(1))}

    m_type_and_send = re.match(r"^type\s+(.+?)\s+and\s+send(?:\s+it)?$", text, re.IGNORECASE)
    if m_type_and_send:
        return {"type": "send_active", "app": None, "recipient": None, "message": clean_msg(m_type_and_send.group(1))}

    # 4. App-first patterns:
    # "send message on <app> to <recipient> <message>"
    # "send message on <app> <message>"
    # "message on <app> to <recipient> <message>"
    # "message on <app> <message>"
    m_app_first = re.match(
        r"^(?:send\s+)?(?:a\s+)?(?:text\s+|message\s+|msg\s+)?on\s+([a-zA-Z0-9_\+]+)\s+(?:to\s+([a-zA-Z0-9_\+]+)\s+)?(?:saying|that|with|message\s+is)?[\s,:\-]*(.+)$",
        text,
        re.IGNORECASE,
    )
    if m_app_first:
        app = resolve_app(m_app_first.group(1))
        recip = m_app_first.group(2).strip() if m_app_first.group(2) else None
        msg = clean_msg(m_app_first.group(3))
        if msg:
            return {"type": "send_app", "app": app, "recipient": recip, "message": msg}

    # 4b. "send <app> [message/text] to <recipient> <message>"
    # e.g., "send whatsapp message to Rohan hello how are you", "send telegram to alex meeting now"
    m_send_app_to = re.match(
        r"^send\s+([a-zA-Z0-9_\+]+)\s+(?:a\s+)?(?:text\s+|message\s+|msg\s+)?to\s+([a-zA-Z0-9_\+]+)\s+(?:saying|that|with|message\s+is)?[\s,:\-]*(.+)$",
        text,
        re.IGNORECASE,
    )
    if m_send_app_to and resolve_app(m_send_app_to.group(1)) in KNOWN_APPS:
        app = resolve_app(m_send_app_to.group(1))
        recip = m_send_app_to.group(2).strip()
        msg = clean_msg(m_send_app_to.group(3))
        if recip and msg:
            return {"type": "send_app", "app": app, "recipient": recip, "message": msg}

    # 5. "send [message/text] to <recipient> [on <app>] <message>"
    # e.g., "send message to moona hello", "send to moona on whatsapp hello", "send a message to moona saying hello"
    m_send_to = re.match(
        r"^send\s+(?:a\s+)?(?:text\s+|message\s+|msg\s+)?to\s+([a-zA-Z0-9_\+]+)(?:\s+on\s+([a-zA-Z0-9_\+]+))?\s+(?:a\s+)?(?:text\s+|message\s+|msg\s+)?(?:saying|that|with|message\s+is)?[\s,:\-]*(.+)$",
        text,
        re.IGNORECASE,
    )
    if m_send_to:
        recip = m_send_to.group(1).strip()
        app_spec = m_send_to.group(2)
        app = resolve_app(app_spec)
        msg = clean_msg(m_send_to.group(3))
        if recip and msg:
            return {"type": "send_app", "app": app, "recipient": recip, "message": msg}

    # 6. "send <recipient> a message/text [on <app>] [saying] <message>"
    # e.g., "send moona a message hello", "send alex a text on telegram hello"
    m_send_recip_msg = re.match(
        r"^send\s+([a-zA-Z0-9_\+]+)\s+(?:a\s+)?(?:text\s+|message\s+|msg\s+)(?:on\s+([a-zA-Z0-9_\+]+)\s+)?(?:saying|that|with|message\s+is)?[\s,:\-]*(.+)$",
        text,
        re.IGNORECASE,
    )
    if m_send_recip_msg:
        recip = m_send_recip_msg.group(1).strip()
        app_spec = m_send_recip_msg.group(2)
        app = resolve_app(app_spec)
        msg = clean_msg(m_send_recip_msg.group(3))
        if recip and msg and recip.lower() not in ("a", "the", "to", "message", "text", "msg"):
            return {"type": "send_app", "app": app, "recipient": recip, "message": msg}

    # 7. "send <message> to <recipient> [on <app>]"
    # Recipient is at the end: 1-2 words.
    # e.g., "send hello to moona", "send I am on my way to moona on whatsapp", "send hello to alex on telegram"
    m_msg_then_to = re.match(
        r"^send\s+(?:a\s+)?(?:text\s+|message\s+|msg\s+)?(.+?)\s+to\s+([a-zA-Z0-9_\+]+(?:\s+[a-zA-Z0-9_\+]+)?)(?:\s+on\s+([a-zA-Z0-9_\+]+))?$",
        text,
        re.IGNORECASE,
    )
    if m_msg_then_to:
        msg = clean_msg(m_msg_then_to.group(1))
        recip = m_msg_then_to.group(2).strip()
        app_spec = m_msg_then_to.group(3)
        app = resolve_app(app_spec)
        if recip.lower() not in ("me", "him", "her", "them", "us", "a", "the"):
            return {"type": "send_app", "app": app, "recipient": recip, "message": msg}

    # 8. "tell <recipient> [that/saying/with] <message>"
    m_tell = re.match(
        r"^tell\s+([a-zA-Z0-9_\+]+)\s+(?:that|saying|with|message\s+is)?[\s,:\-]*(.+)$",
        text,
        re.IGNORECASE,
    )
    if m_tell:
        recip = m_tell.group(1).strip()
        msg = clean_msg(m_tell.group(2))
        if recip and msg and recip.lower() not in ("me", "him", "her", "them", "us", "a", "the", "story", "joke", "about"):
            return {"type": "send_app", "app": "whatsapp", "recipient": recip, "message": msg}

    # 9. Direct verb: "message/text/dm/whatsapp/telegram <recipient> [on <app>] <message>"
    m_direct_verb = re.match(
        r"^(?:message|text|msg|dm|whatsapp|telegram)\s+([a-zA-Z0-9_\+]+)\s+(?:on\s+([a-zA-Z0-9_\+]+)\s+)?(?:saying|that|with)?[\s,:\-]*(.+)$",
        text,
        re.IGNORECASE,
    )
    if m_direct_verb:
        recip = m_direct_verb.group(1).strip()
        app_spec = m_direct_verb.group(2)
        msg = clean_msg(m_direct_verb.group(3))
        default_app = "telegram" if "telegram" in text.lower() else "whatsapp"
        app = resolve_app(app_spec) if app_spec else default_app
        if recip.lower() not in ("message", "text", "msg", "whatsapp", "telegram", "discord", "slack", "a", "the"):
            if recip and msg:
                return {"type": "send_app", "app": app, "recipient": recip, "message": msg}

    # 10. Simple: "send <recipient> <message>" (e.g. "send moona hello")
    m_send_simple = re.match(
        r"^send\s+([a-zA-Z0-9_\+]+)\s+(?:saying|that|with)?[\s,:\-]+(.+)$",
        text,
        re.IGNORECASE,
    )
    if m_send_simple:
        recip = m_send_simple.group(1).strip()
        msg = clean_msg(m_send_simple.group(2))
        if recip.lower() not in ("message", "text", "msg", "whatsapp", "telegram", "discord", "slack", "a", "the", "hello", "hi", "hey", "ok", "yes", "no"):
            if recip and msg:
                return {"type": "send_app", "app": "whatsapp", "recipient": recip, "message": msg}

    # 11. Active window message dispatch:
    # "send message <message>"
    # "send text <message>"
    # "send a message <message>"
    # "message <message>"
    m_active = re.match(
        r"^(?:send\s+)?(?:a\s+)?(?:text|message|msg)\s+(?:saying\s+)?(.+)$",
        text,
        re.IGNORECASE,
    )
    if m_active:
        msg = clean_msg(m_active.group(1))
        if msg:
            return {"type": "send_active", "app": None, "recipient": None, "message": msg}

    # 12. Bare "send <short_msg>" (e.g. "send hello", "send ok")
    m_bare_send = re.match(r"^send\s+([a-zA-Z0-9_\s'\",\.\?!]{1,40})$", text, re.IGNORECASE)
    if m_bare_send:
        msg = clean_msg(m_bare_send.group(1))
        if msg.lower() not in ("it", "this", "that", "file", "files", "email", "mail"):
            return {"type": "send_active", "app": None, "recipient": None, "message": msg}

    return None



def send_app_message(
    app: Optional[str],
    recipient: Optional[str],
    message: str,
    auto_send: bool = True,
) -> Dict[str, Any]:
    """Universally send a message to a recipient or active chat on any desktop application.

    Args:
        app: Target application name ('whatsapp', 'telegram', 'discord', 'slack', 'teams', 'skype', etc.)
             or None for currently focused active window.
        recipient: Contact name, username, or channel name (or None for currently active chat in that app).
        message: The text to send.
        auto_send: If True, dispatches the message with Enter.
    """
    if not message or not message.strip():
        return {"success": False, "output": "Message text is required."}

    msg_clean = message.strip()
    recip_clean = recipient.strip() if recipient else ""
    target_app = (app or "").lower().strip()

    logger.info(f"Universal messaging dispatch: app='{target_app}', recipient='{recip_clean}', message='{msg_clean}'")

    # --------------------------------------------------------------------------
    # 1. WhatsApp
    # --------------------------------------------------------------------------
    if target_app in ("whatsapp", "wa"):
        from z3ro.messaging.whatsapp import send_whatsapp, open_whatsapp
        if recip_clean:
            return send_whatsapp(recip_clean, msg_clean, auto_send=auto_send)
        else:
            open_whatsapp()
            time.sleep(0.5)
            focus_window("WhatsApp")
            time.sleep(0.2)
            pyperclip.copy(msg_clean)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.1)
            if auto_send:
                pyautogui.press("enter")
            return {"success": True, "output": f"Sent WhatsApp message: \"{msg_clean}\""}

    # --------------------------------------------------------------------------
    # 2. Telegram
    # --------------------------------------------------------------------------
    if target_app in ("telegram", "tg"):
        from z3ro.messaging.telegram import send_telegram
        return send_telegram(recip_clean, msg_clean, auto_send=auto_send)

    # --------------------------------------------------------------------------
    # 3. Discord
    # --------------------------------------------------------------------------
    if target_app == "discord":
        try:
            w = find_window("Discord")
            if not w:
                logger.info("Launching Discord...")
                open_app("discord")
                time.sleep(2.5)
            focus_window("Discord")
            time.sleep(0.3)

            if recip_clean:
                # Use Quick Switcher (Ctrl+K) to find friend or channel
                pyautogui.press("esc")
                time.sleep(0.1)
                pyautogui.hotkey("ctrl", "k")
                time.sleep(0.3)
                pyperclip.copy(recip_clean)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.6)
                pyautogui.press("enter")
                time.sleep(0.5)

            pyperclip.copy(msg_clean)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.1)
            if auto_send:
                pyautogui.press("enter")

            dest = f" to {recip_clean}" if recip_clean else ""
            return {"success": True, "output": f"Sent Discord message{dest}: \"{msg_clean}\""}
        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")
            return {"success": False, "output": f"Failed to send Discord message: {e}"}

    # --------------------------------------------------------------------------
    # 4. Slack
    # --------------------------------------------------------------------------
    if target_app == "slack":
        try:
            w = find_window("Slack")
            if not w:
                logger.info("Launching Slack...")
                open_app("slack")
                time.sleep(2.5)
            focus_window("Slack")
            time.sleep(0.3)

            if recip_clean:
                # Use Quick Switcher (Ctrl+K) in Slack
                pyautogui.press("esc")
                time.sleep(0.1)
                pyautogui.hotkey("ctrl", "k")
                time.sleep(0.3)
                pyperclip.copy(recip_clean)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.6)
                pyautogui.press("enter")
                time.sleep(0.5)

            pyperclip.copy(msg_clean)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.1)
            if auto_send:
                pyautogui.press("enter")

            dest = f" to {recip_clean}" if recip_clean else ""
            return {"success": True, "output": f"Sent Slack message{dest}: \"{msg_clean}\""}
        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}")
            return {"success": False, "output": f"Failed to send Slack message: {e}"}

    # --------------------------------------------------------------------------
    # 5. Microsoft Teams
    # --------------------------------------------------------------------------
    if target_app in ("teams", "microsoft teams", "ms teams"):
        try:
            w = find_window("Teams")
            if not w:
                logger.info("Launching Teams...")
                open_app("teams")
                time.sleep(2.5)
            focus_window("Teams")
            time.sleep(0.3)

            if recip_clean:
                # Use Ctrl+G / Ctrl+E in Teams to search/go to chat
                pyautogui.hotkey("ctrl", "g")
                time.sleep(0.3)
                pyperclip.copy(recip_clean)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.6)
                pyautogui.press("enter")
                time.sleep(0.5)

            pyperclip.copy(msg_clean)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.1)
            if auto_send:
                pyautogui.press("enter")

            dest = f" to {recip_clean}" if recip_clean else ""
            return {"success": True, "output": f"Sent Teams message{dest}: \"{msg_clean}\""}
        except Exception as e:
            logger.error(f"Failed to send Teams message: {e}")
            return {"success": False, "output": f"Failed to send Teams message: {e}"}

    # --------------------------------------------------------------------------
    # 6. Skype
    # --------------------------------------------------------------------------
    if target_app == "skype":
        try:
            w = find_window("Skype")
            if not w:
                logger.info("Launching Skype...")
                open_app("skype")
                time.sleep(2.0)
            focus_window("Skype")
            time.sleep(0.3)

            if recip_clean:
                pyautogui.hotkey("ctrl", "f")
                time.sleep(0.3)
                pyperclip.copy(recip_clean)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.6)
                pyautogui.press("enter")
                time.sleep(0.5)

            pyperclip.copy(msg_clean)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.1)
            if auto_send:
                pyautogui.press("enter")

            dest = f" to {recip_clean}" if recip_clean else ""
            return {"success": True, "output": f"Sent Skype message{dest}: \"{msg_clean}\""}
        except Exception as e:
            logger.error(f"Failed to send Skype message: {e}")
            return {"success": False, "output": f"Failed to send Skype message: {e}"}

    # --------------------------------------------------------------------------
    # 7. Other Named Apps (Instagram, Messenger, Signal, Notepad, Chrome, etc.)
    # --------------------------------------------------------------------------
    if target_app:
        try:
            w = find_window(target_app)
            if not w:
                logger.info(f"Launching {target_app}...")
                open_app(target_app)
                time.sleep(2.0)
            focus_window(target_app)
            time.sleep(0.3)

            if recip_clean:
                # Generic search shortcut
                pyautogui.hotkey("ctrl", "f")
                time.sleep(0.3)
                pyperclip.copy(recip_clean)
                pyautogui.hotkey("ctrl", "v")
                time.sleep(0.5)
                pyautogui.press("enter")
                time.sleep(0.5)

            pyperclip.copy(msg_clean)
            pyautogui.hotkey("ctrl", "v")
            time.sleep(0.1)
            if auto_send:
                pyautogui.press("enter")

            dest = f" to {recip_clean}" if recip_clean else ""
            return {"success": True, "output": f"Sent message{dest} on {target_app}: \"{msg_clean}\""}
        except Exception as e:
            logger.error(f"Failed to send message on {target_app}: {e}")
            return {"success": False, "output": f"Failed to send message on {target_app}: {e}"}

    # --------------------------------------------------------------------------
    # 8. Active Focused Window (No app specified or active-window dispatch)
    # --------------------------------------------------------------------------
    logger.info(f"Injecting message directly into currently focused window...")
    res = type_text(text=msg_clean, press_enter=auto_send)
    if res.success:
        return {"success": True, "output": f"Sent message: \"{msg_clean}\""}
    else:
        return {"success": False, "output": f"Failed to send message: {res.output}"}
