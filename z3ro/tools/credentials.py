"""credentials.py — Scoped credential broker (Section 9.3). Instead of giving
the agent your real Stripe secret key, AdSense token, etc. directly, the
agent asks THIS module for a capability, and this module hands back only
what's needed, checked against limits.py first.

For real virtual-card issuance (e.g. Privacy.com, Wise), plug their API
calls into issue_virtual_card() below. This starter version demonstrates
the pattern with a mock capped-card record so you can wire a real provider
in one place.
"""

import os
import uuid
import time
import sqlite3
import threading
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Tuple, Dict, List

from ..economy import limits

DB_PATH = Path(__file__).parent.parent / "economy" / "credentials_log.db"


@dataclass
class ScopedCredential:
    cred_id: str
    kind: str  # 'api_key_readonly', 'virtual_card', 'oauth_token'
    scope: str  # human-readable description of what it can do
    cap_amount: float  # 0 if not a spending credential
    expires_at: float  # unix timestamp
    value: str = ""  # the actual secret/token — never log this in plaintext elsewhere
    revoked: bool = False
    description: str = ""
    issued_at: float = field(default_factory=time.time)

    @property
    def token_id(self) -> str:
        return self.cred_id

    @property
    def max_amount_cap(self) -> float:
        return self.cap_amount

    @property
    def is_revoked(self) -> bool:
        return self.revoked

    @is_revoked.setter
    def is_revoked(self, val: bool):
        self.revoked = val

    def is_valid(self, requested_cost: float = 0.0) -> Tuple[bool, str]:
        if self.revoked:
            return False, "Credential has been revoked."
        if time.time() > self.expires_at:
            return False, f"Credential expired {int(time.time() - self.expires_at)}s ago."
        if requested_cost > self.cap_amount:
            return False, f"Requested cost ${requested_cost:.2f} exceeds credential cap of ${self.cap_amount:.2f}."
        return True, "VALID"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS credential_issuance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL NOT NULL,
        cred_id TEXT NOT NULL,
        kind TEXT,
        scope TEXT,
        cap_amount REAL,
        strategy_id TEXT,
        revoked INTEGER DEFAULT 0
    )
    """)
    conn.commit()
    return conn


def issue_readonly_api_token(service: str, strategy_id: str) -> ScopedCredential:
    """Returns a read-only token for research/verification purposes
    (e.g. YouTube Analytics read scope). Pulls the real token from env vars
    that YOU configured — the agent never sees how to generate one itself.
    """
    env_var = f"{service.upper()}_READONLY_TOKEN"
    token = os.environ.get(env_var)
    if not token:
        raise PermissionError(f"No readonly token configured for {service}. Set {env_var}.")
    cred_id = str(uuid.uuid4())
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO credential_issuance (timestamp, cred_id, kind, scope, cap_amount, strategy_id) "
            "VALUES (?,?,?,?,?,?)",
            (time.time(), cred_id, "api_key_readonly", f"{service}:read", 0, strategy_id),
        )
        conn.commit()
    finally:
        conn.close()

    return ScopedCredential(
        cred_id=cred_id,
        kind="api_key_readonly",
        scope=f"{service}:read",
        cap_amount=0.0,
        expires_at=time.time() + 3600,
        value=token,
    )


def issue_virtual_card(amount_needed: float, strategy_id: str) -> ScopedCredential:
    """Issue a spend-capped virtual card for the agent to use for a specific
    purchase (e.g. hosting, domain registration). Checks limits.py first.
    Wire a real provider here, e.g.:
    - Privacy.com API: create a single-use card with `spend_limit=amount_needed`
    - Wise API: create a disposable card with a matching limit
    This starter version raises if no real provider is configured, so you
    don't accidentally think a mock card is a real one.
    """
    allowed, reason = limits.check_spend_allowed(amount_needed, strategy_id)
    if not allowed:
        raise PermissionError(f"Spend denied by limits.py: {reason}")
    provider_api_key = os.environ.get("VIRTUAL_CARD_PROVIDER_KEY")
    if not provider_api_key:
        raise PermissionError(
            "No virtual card provider configured. Set VIRTUAL_CARD_PROVIDER_KEY "
            "and implement the real API call in issue_virtual_card() before "
            "the agent can spend real money."
        )
    # --- Real integration goes here, e.g.: ---
    # resp = requests.post("https://api.privacy.com/v1/card", ...,
    # json={"spend_limit": int(amount_needed*100), ...})
    # card_number = resp.json()["card_number"]
    raise NotImplementedError(
        "Plug in your real virtual-card provider's API call above this line."
    )


def revoke(cred_id: str):
    conn = _connect()
    try:
        conn.execute("UPDATE credential_issuance SET revoked=1 WHERE cred_id=?", (cred_id,))
        conn.commit()
    finally:
        conn.close()


def list_issued(limit: int = 50):
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT timestamp, cred_id, kind, scope, cap_amount, strategy_id, revoked "
            "FROM credential_issuance ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return rows
    finally:
        conn.close()


class CredentialBroker:
    """Central manager of short-lived, scoped credentials."""

    def __init__(self):
        self._lock = threading.Lock()
        self._active_tokens: Dict[str, ScopedCredential] = {}

    def issue_credential(
        self,
        scope: str,
        max_amount_cap: float = 0.0,
        ttl_seconds: float = 300.0,  # Default 5 minutes TTL
        description: str = "",
    ) -> ScopedCredential:
        """Issue a new temporary, scoped credential."""
        token_id = f"token_{uuid.uuid4().hex[:12]}"
        now = time.time()
        cred = ScopedCredential(
            cred_id=token_id,
            kind="token",
            scope=scope,
            cap_amount=max_amount_cap,
            expires_at=now + ttl_seconds,
            revoked=False,
            description=description,
            issued_at=now,
        )
        with self._lock:
            self._active_tokens[token_id] = cred
        return cred

    def validate(self, token_id: str, required_scope: str, cost: float = 0.0) -> Tuple[bool, str]:
        """Validate if a credential token is valid for the requested scope and cost."""
        with self._lock:
            cred = self._active_tokens.get(token_id)
            if not cred:
                return False, "Unrecognized or invalid token ID."
            if cred.scope != required_scope and cred.scope != "SUPER_ADMIN":
                return False, f"Scope mismatch. Required '{required_scope}', got '{cred.scope}'."
            return cred.is_valid(cost)

    def revoke(self, token_id: str) -> bool:
        """Centrally revoke a credential immediately."""
        revoke(token_id)
        with self._lock:
            if token_id in self._active_tokens:
                self._active_tokens[token_id].revoked = True
                return True
            return False

    def revoke_all(self):
        """Emergency revoke all issued credentials."""
        with self._lock:
            for cred in self._active_tokens.values():
                cred.revoked = True

    def get_active_count(self) -> int:
        now = time.time()
        with self._lock:
            return sum(
                1 for c in self._active_tokens.values()
                if not c.revoked and c.expires_at > now
            )


# Global credential broker singleton
credential_broker = CredentialBroker()


if __name__ == "__main__":
    for r in list_issued(10):
        print(r)
