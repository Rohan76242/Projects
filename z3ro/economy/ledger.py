"""ledger.py — Append-only financial ledger.

Design rule: the agent (planner/brain) NEVER calls record_income() directly.
Only verifier.py may call record_income(), and only after it has confirmed
the income against a real third-party source. This file enforces that by
requiring an `evidence` object on every income entry.

The agent CAN call record_cost() for its own spending, but only up to the
caps defined in limits.py (checked by the caller, e.g. tools/credentials.py).
"""

import sqlite3
import time
import json
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

DB_PATH = Path(__file__).parent / "ledger.db"
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
ECONOMY_DB_PATH = DATA_DIR / "z3ro_economy.db"


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL NOT NULL,
        entry_type TEXT NOT NULL, -- 'income' or 'cost'
        amount REAL NOT NULL,
        strategy_id TEXT,
        description TEXT,
        evidence_source TEXT, -- e.g. 'youtube_adsense_api', 'amazon_associates_api'
        evidence_id TEXT, -- the third-party's own transaction/report ID
        evidence_raw TEXT, -- json blob of the raw API response, for audit
        verified INTEGER NOT NULL DEFAULT 0
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL NOT NULL,
        amount REAL NOT NULL,
        destination TEXT,
        initiated_by TEXT NOT NULL DEFAULT 'human', -- always 'human' — enforced below
        note TEXT
    )
    """)
    conn.commit()
    return conn


def record_income(
    amount: float,
    strategy_id: str,
    description: str,
    evidence_source: str,
    evidence_id: str,
    evidence_raw: dict,
):
    """Record VERIFIED income only. Called exclusively by verifier.py after
    it has confirmed money actually moved via a third-party API/webhook.
    """
    if not evidence_source or not evidence_id:
        raise ValueError(
            "Refusing to record income without evidence_source and evidence_id. "
            "Unverified income must never enter the ledger."
        )
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO ledger (timestamp, entry_type, amount, strategy_id, description, "
            "evidence_source, evidence_id, evidence_raw, verified) VALUES (?,?,?,?,?,?,?,?,1)",
            (
                time.time(),
                "income",
                amount,
                strategy_id,
                description,
                evidence_source,
                evidence_id,
                json.dumps(evidence_raw),
            ),
        )
        conn.commit()
    finally:
        conn.close()

    # Mirror to central economy db if active
    try:
        ledger.record_entry(
            action=description,
            cost=0.0,
            verified_income=amount,
            evidence_id=evidence_id,
            verification_source=evidence_source,
            status="VERIFIED",
        )
    except Exception:
        pass


def record_cost(amount: float, strategy_id: str, description: str):
    """Record agent spending. Caller (credentials.py) must enforce spend caps BEFORE this."""
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO ledger (timestamp, entry_type, amount, strategy_id, description, verified) "
            "VALUES (?,?,?,?,?,1)",
            (time.time(), "cost", -abs(amount), strategy_id, description),
        )
        conn.commit()
    finally:
        conn.close()

    # Mirror to central economy db if active
    try:
        ledger.record_entry(
            action=description,
            cost=abs(amount),
            verified_income=0.0,
            evidence_id=strategy_id,
            verification_source="CREDENTIAL_SPEND",
            status="VERIFIED",
        )
    except Exception:
        pass


def record_withdrawal(amount: float, destination: str, note: str = ""):
    """Record a withdrawal to the user's real bank/account.
    initiated_by is hard-coded to 'human' — this function should only ever
    be called from a manual script or dashboard button the AGENT cannot trigger.
    """
    conn = _connect()
    try:
        conn.execute(
            "INSERT INTO withdrawals (timestamp, amount, destination, initiated_by, note) "
            "VALUES (?,?,?,?,?)",
            (time.time(), amount, destination, "human", note),
        )
        conn.commit()
    finally:
        conn.close()


def get_verified_balance() -> float:
    """Total verified net resources currently available (income - costs - withdrawals)."""
    conn = _connect()
    try:
        income_cost = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM ledger WHERE verified = 1"
        ).fetchone()[0]
        withdrawn = conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM withdrawals"
        ).fetchone()[0]
        return round(income_cost - withdrawn, 2)
    finally:
        conn.close()


def get_history(limit: int = 50):
    conn = _connect()
    try:
        rows = conn.execute(
            "SELECT timestamp, entry_type, amount, strategy_id, description, evidence_source, evidence_id "
            "FROM ledger ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return rows
    finally:
        conn.close()


class Ledger:
    """Thread-safe, append-only SQLite ledger for Z3RO's economic tracking."""

    def __init__(self, db_path: Path = ECONOMY_DB_PATH):
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
                    CREATE TABLE IF NOT EXISTS ledger (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        action TEXT NOT NULL,
                        cost REAL NOT NULL DEFAULT 0.0,
                        verified_income REAL NOT NULL DEFAULT 0.0,
                        net REAL NOT NULL DEFAULT 0.0,
                        evidence_id TEXT,
                        verification_source TEXT NOT NULL,
                        status TEXT NOT NULL DEFAULT 'VERIFIED'
                    )
                """)
                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_ledger_timestamp
                    ON ledger (timestamp DESC)
                """)

    def record_entry(
        self,
        action: str,
        cost: float = 0.0,
        verified_income: float = 0.0,
        evidence_id: Optional[str] = None,
        verification_source: str = "INTERNAL_SIMULATION",
        status: str = "VERIFIED",
    ) -> int:
        """Append an entry to the immutable ledger."""
        net = round(verified_income - cost, 4)
        timestamp = datetime.now().isoformat()

        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO ledger (
                        timestamp, action, cost, verified_income, net, evidence_id, verification_source, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    timestamp,
                    action,
                    round(cost, 4),
                    round(verified_income, 4),
                    net,
                    evidence_id or "",
                    verification_source,
                    status,
                ))
                return cursor.lastrowid or -1

    def get_summary(self) -> Dict[str, float]:
        """Compute verified financial summary: total revenue, total costs, net profit."""
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT 
                        COALESCE(SUM(verified_income), 0.0) as total_revenue,
                        COALESCE(SUM(cost), 0.0) as total_cost,
                        COALESCE(SUM(net), 0.0) as net_profit,
                        COUNT(id) as total_entries
                    FROM ledger
                """)
                row = cursor.fetchone()
                return {
                    "total_revenue": round(float(row["total_revenue"]), 2),
                    "total_cost": round(float(row["total_cost"]), 2),
                    "net_profit": round(float(row["net_profit"]), 2),
                    "total_entries": int(row["total_entries"]),
                }

    def get_recent_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch the most recent ledger entries in reverse chronological order."""
        with self._lock:
            with self._connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, timestamp, action, cost, verified_income, net, evidence_id, verification_source, status
                    FROM ledger
                    ORDER BY id DESC
                    LIMIT ?
                """, (limit,))
                return [dict(row) for row in cursor.fetchall()]


# Global singleton instance
ledger = Ledger()


if __name__ == "__main__":
    print("Current verified balance:", get_verified_balance())
    print("Recent entries:")
    for r in get_history(10):
        print(r)
