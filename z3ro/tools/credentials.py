"""Z3RO — Scoped Credential Broker.

Implements Section 9.3:
- Issues short-lived, narrowly scoped credentials to authorized tools.
- Never hands the agent master keys or banking logins.
- Centrally revocable at any moment.
- Enforces per-transaction caps and expiration time-to-live (TTL).
"""

import time
import uuid
import threading
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Set


@dataclass
class ScopedCredential:
    token_id: str
    scope: str
    max_amount_cap: float
    issued_at: float
    expires_at: float
    is_revoked: bool = False
    description: str = ""

    def is_valid(self, requested_cost: float = 0.0) -> Tuple[bool, str]:
        if self.is_revoked:
            return False, "Credential has been revoked."
        if time.time() > self.expires_at:
            return False, f"Credential expired {int(time.time() - self.expires_at)}s ago."
        if requested_cost > self.max_amount_cap:
            return False, f"Requested cost ${requested_cost:.2f} exceeds credential cap of ${self.max_amount_cap:.2f}."
        return True, "VALID"


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
            token_id=token_id,
            scope=scope,
            max_amount_cap=max_amount_cap,
            issued_at=now,
            expires_at=now + ttl_seconds,
            is_revoked=False,
            description=description,
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
        with self._lock:
            if token_id in self._active_tokens:
                self._active_tokens[token_id].is_revoked = True
                return True
            return False

    def revoke_all(self):
        """Emergency revoke all issued credentials."""
        with self._lock:
            for cred in self._active_tokens.values():
                cred.is_revoked = True

    def get_active_count(self) -> int:
        now = time.time()
        with self._lock:
            return sum(
                1 for c in self._active_tokens.values() 
                if not c.is_revoked and c.expires_at > now
            )


# Global credential broker singleton
credential_broker = CredentialBroker()
