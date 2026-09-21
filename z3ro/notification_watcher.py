"""Z3RO / SOBIA — Windows Notification Watcher.

Polls the Windows notification database (wpndatabase.db) for new toast
notifications and announces them via TTS. Runs as a background daemon thread.
"""

import os
import sqlite3
import xml.etree.ElementTree as ET
import threading
import time
from typing import Callable, Optional

from z3ro.logger import logger


# ──────────────────────────────────────────────────────────────────────────────
# Thread-safe last notification context — shared with the agent for reply
# ──────────────────────────────────────────────────────────────────────────────
_last_notification_lock = threading.Lock()
_last_notification: Optional[dict] = None  # {"app": ..., "sender": ..., "message": ..., "timestamp": ...}


def set_last_notification(app: str, sender: str, message: str):
    """Store the most recent notification context for reply routing."""
    global _last_notification
    with _last_notification_lock:
        _last_notification = {
            "app": app,
            "sender": sender,
            "message": message,
            "timestamp": time.time(),
        }


def get_last_notification() -> Optional[dict]:
    """Get the most recent notification context. Returns None if stale (>5 min)."""
    with _last_notification_lock:
        if _last_notification is None:
            return None
        # Expire after 5 minutes
        if time.time() - _last_notification["timestamp"] > 300:
            return None
        return dict(_last_notification)


# Friendly app name mapping from raw Windows AppUserModelIDs
_APP_NAME_MAP = {
    "whatsapp": "WhatsApp",
    "telegram": "Telegram",
    "discord": "Discord",
    "slack": "Slack",
    "skype": "Skype",
    "outlook": "Email",
    "mail": "Email",
    "teams": "Teams",
    "signal": "Signal",
    "instagram": "Instagram",
    "messenger": "Messenger",
    "phonelink": "Phone Link",
    "yourphone": "Phone Link",
    "snapchat": "Snapchat",
    "twitter": "Twitter",
    "chrome": "Chrome",
    "edge": "Edge",
    "firefox": "Firefox",
}


def _resolve_app_name(raw_app_id: str) -> str:
    """Convert a Windows AppUserModelID to a human-friendly app name."""
    if not raw_app_id:
        return "App"
    lower = raw_app_id.lower()
    for key, friendly in _APP_NAME_MAP.items():
        if key in lower:
            return friendly
    # Fallback: extract last segment of the ID
    parts = raw_app_id.replace("\\", "/").split("/")
    name = parts[-1] if parts else raw_app_id
    # Strip common suffixes
    for suffix in (".exe", "!App", "!app", "_8wekyb3d8bbwe"):
        name = name.replace(suffix, "")
    return name.strip() or "App"


def _parse_notification_xml(payload) -> Optional[dict]:
    """Parse a Windows toast notification XML payload into sender + message."""
    if not payload:
        return None
    try:
        xml_text = payload.decode("utf-8", errors="ignore") if isinstance(payload, bytes) else str(payload)
        root = ET.fromstring(xml_text)
        texts = [elem.text for elem in root.iter("text") if elem.text and elem.text.strip()]
        if not texts:
            return None
        sender = texts[0].strip() if len(texts) > 0 else "Someone"
        body = texts[1].strip() if len(texts) > 1 else ""
        return {"sender": sender, "body": body}
    except Exception:
        return None


class NotificationWatcher:
    """Background poller for Windows toast notifications."""

    DB_PATH = os.path.expandvars(
        r"%LOCALAPPDATA%\Microsoft\Windows\Notifications\wpndatabase.db"
    )

    def __init__(
        self,
        on_notification: Callable[[str, str, str], None],
        poll_interval: float = 3.0,
    ):
        """
        Args:
            on_notification: Callback(app_name, sender, message) called for each new notification.
            poll_interval: Seconds between database polls.
        """
        self._callback = on_notification
        self._poll_interval = poll_interval
        self._last_seen_id: int = 0
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def _init_last_seen_id(self):
        """Set the baseline to the current max notification ID so we only announce NEW ones."""
        try:
            conn = sqlite3.connect(f"file:{self.DB_PATH}?mode=ro", uri=True, timeout=2)
            c = conn.cursor()
            c.execute("SELECT MAX(Id) FROM Notification WHERE Type = 'toast'")
            row = c.fetchone()
            conn.close()
            self._last_seen_id = row[0] if row and row[0] else 0
            logger.info(f"Notification watcher baseline ID: {self._last_seen_id}")
        except Exception as e:
            logger.debug(f"Could not read notification DB baseline: {e}")
            self._last_seen_id = 0

    def _poll_once(self):
        """Check for new notifications since last_seen_id."""
        try:
            conn = sqlite3.connect(f"file:{self.DB_PATH}?mode=ro", uri=True, timeout=2)
            c = conn.cursor()
            c.execute(
                """
                SELECT n.Id, h.PrimaryId, n.Payload
                FROM Notification n
                LEFT JOIN NotificationHandler h ON n.HandlerId = h.RecordId
                WHERE n.Type = 'toast' AND n.Id > ?
                ORDER BY n.Id ASC
                LIMIT 5
                """,
                (self._last_seen_id,),
            )
            rows = c.fetchall()
            conn.close()
        except Exception as e:
            logger.debug(f"Notification poll error: {e}")
            return

        for nid, app_id, payload in rows:
            self._last_seen_id = max(self._last_seen_id, nid)
            parsed = _parse_notification_xml(payload)
            if not parsed:
                continue
            app_name = _resolve_app_name(app_id or "")
            sender = parsed["sender"]
            body = parsed["body"]
            if not body:
                continue
            try:
                self._callback(app_name, sender, body)
            except Exception as e:
                logger.error(f"Notification callback error: {e}")

    def _run_loop(self):
        """Main polling loop running in a background thread."""
        self._init_last_seen_id()
        while self._running:
            self._poll_once()
            time.sleep(self._poll_interval)

    def start(self):
        """Start the notification watcher in a background daemon thread."""
        if self._running:
            return
        if not os.path.isfile(self.DB_PATH):
            logger.warning(f"Notification database not found: {self.DB_PATH}")
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="NotificationWatcher")
        self._thread.start()
        logger.info("Notification watcher started.")

    def stop(self):
        """Stop the notification watcher."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None
        logger.info("Notification watcher stopped.")
