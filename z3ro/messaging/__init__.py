"""Z3RO / SOBIA — Messaging Module.

Provides native messaging capabilities for WhatsApp and Telegram on Windows.
"""

from z3ro.messaging.whatsapp import send_whatsapp, open_whatsapp
from z3ro.messaging.telegram import send_telegram, open_telegram

__all__ = [
    "send_whatsapp",
    "open_whatsapp",
    "send_telegram",
    "open_telegram",
]
