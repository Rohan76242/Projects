"""Z3RO — Communication Tool & Human Approval Queue.

Implements Section 9.1 & 9.6:
- Capability: 'send_external_message' (Restricted, Requires human approval).
- Irreversible external actions route to human approval queue.
- Integrates with UI Dashboard approval buttons (Approve / Reject).
"""

import time
import uuid
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any

from z3ro.economy.limits import limits_manager, ActionReversibility
from z3ro.economy.ledger import ECONOMY_DB_PATH
import sqlite3


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


@dataclass
class PendingApprovalAction:
    action_id: str
    capability: str
    recipient: str
    message: str
    reversibility: str
    estimated_cost: float
    created_at: float
    status: ApprovalStatus = ApprovalStatus.PENDING
    resolution_notes: str = ""


class ApprovalQueue:
    """Thread-safe queue for actions requiring human authorization."""

    def __init__(self, db_path=ECONOMY_DB_PATH):
        self.db_path = db_path
        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _connection(self):
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS pending_approvals (
                        action_id TEXT PRIMARY KEY,
                        capability TEXT NOT NULL,
                        recipient TEXT,
                        message TEXT NOT NULL,
                        reversibility TEXT NOT NULL,
                        estimated_cost REAL NOT NULL DEFAULT 0.0,
                        created_at REAL NOT NULL,
                        status TEXT NOT NULL DEFAULT 'PENDING',
                        resolution_notes TEXT DEFAULT ''
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_approvals_status
                    ON pending_approvals (status)
                """)

    def submit_for_approval(
        self,
        capability: str,
        recipient: str,
        message: str,
        estimated_cost: float = 0.0,
    ) -> PendingApprovalAction:
        """Enqueue an external action for human review."""
        action_id = f"appr_{uuid.uuid4().hex[:10]}"
        now = time.time()
        reversibility = limits_manager.classify_reversibility(capability).value

        item = PendingApprovalAction(
            action_id=action_id,
            capability=capability,
            recipient=recipient,
            message=message,
            reversibility=reversibility,
            estimated_cost=estimated_cost,
            created_at=now,
            status=ApprovalStatus.PENDING,
        )

        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO pending_approvals (
                        action_id, capability, recipient, message, reversibility, estimated_cost, created_at, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    action_id,
                    capability,
                    recipient,
                    message,
                    reversibility,
                    estimated_cost,
                    now,
                    ApprovalStatus.PENDING.value,
                ))
        return item

    def resolve_action(self, action_id: str, approved: bool, notes: str = "") -> bool:
        """Human approval or rejection from UI."""
        status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE pending_approvals
                    SET status = ?, resolution_notes = ?
                    WHERE action_id = ? AND status = 'PENDING'
                """, (status.value, notes, action_id))
                return cursor.rowcount > 0

    def get_pending(self) -> List[Dict[str, Any]]:
        """Retrieve all currently pending approvals."""
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT action_id, capability, recipient, message, reversibility, estimated_cost, created_at, status
                    FROM pending_approvals
                    WHERE status = 'PENDING'
                    ORDER BY created_at DESC
                """)
                return [dict(row) for row in cursor.fetchall()]

    def get_action(self, action_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM pending_approvals WHERE action_id = ?", (action_id,))
                row = cursor.fetchone()
                return dict(row) if row else None


class CommunicationTool:
    """Sends external messages with strict permission table and approval queue integration."""

    def __init__(self, approval_queue: ApprovalQueue = None):
        self.approval_queue = approval_queue or ApprovalQueue()

    def request_dispatch(
        self,
        capability: str,
        recipient: str,
        message: str,
        estimated_cost: float = 0.0,
    ) -> Dict[str, Any]:
        """Request to send an external message or notification."""
        # 1. Check if allowed directly or needs approval
        allowed, reason = limits_manager.check_can_execute(
            capability=capability,
            cost=estimated_cost,
            is_human_approved=False,
        )

        if not allowed:
            # Enqueue into Pending Approvals for human review
            item = self.approval_queue.submit_for_approval(
                capability=capability,
                recipient=recipient,
                message=message,
                estimated_cost=estimated_cost,
            )
            return {
                "success": False,
                "status": "QUEUED_FOR_APPROVAL",
                "action_id": item.action_id,
                "reversibility": item.reversibility,
                "message": f"Action requires human approval: {reason}. Enqueued as {item.action_id}.",
            }

        # If already allowed (e.g. approved), proceed to execution
        return self._dispatch_direct(recipient, message)

    def execute_approved_action(self, action_id: str) -> Dict[str, Any]:
        """Dispatch an action that has been approved by the user."""
        action = self.approval_queue.get_action(action_id)
        if not action or action["status"] != ApprovalStatus.APPROVED.value:
            return {"success": False, "error": f"Action {action_id} is not approved."}

        recipient = action["recipient"]
        message = action["message"]
        limits_manager.record_action_executed(action["estimated_cost"])
        return self._dispatch_direct(recipient, message)

    def _dispatch_direct(self, recipient: str, message: str) -> Dict[str, Any]:
        return {
            "success": True,
            "recipient": recipient,
            "status": "DISPATCHED",
            "timestamp": time.time(),
        }


# Global communication and approvals singleton
approval_queue = ApprovalQueue()
communication_tool = CommunicationTool(approval_queue=approval_queue)
