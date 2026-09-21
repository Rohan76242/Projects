"""Z3RO — Local-First SQLite History & State Store.

Provides high-performance, zero-latency local logging and full-text search
for past interactions, prompt history, and clipboard operations.
"""

import os
import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Database path in z3ro/data/
DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "z3ro_history.db"


def _get_connection() -> sqlite3.Connection:
    """Get a thread-safe SQLite connection with row factory enabled."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize SQLite schema for local interactions and FTS search."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        
        # Primary interactions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                mode TEXT NOT NULL DEFAULT 'ask',
                query TEXT NOT NULL,
                response TEXT NOT NULL,
                action_type TEXT DEFAULT 'chat',
                pinned INTEGER DEFAULT 0
            )
        """)

        # Index for ultra-fast reverse chronological retrieval
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_interactions_timestamp 
            ON interactions (timestamp DESC)
        """)
        
        # Index for mode filtering
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_interactions_mode 
            ON interactions (mode)
        """)

        conn.commit()


# Initialize schema on module import
init_db()


def log_interaction(
    query: str,
    response: str,
    mode: str = "ask",
    action_type: str = "chat",
    pinned: int = 0
) -> int:
    """Log an interaction to local SQLite store and return inserted row ID."""
    if not query.strip() and not response.strip():
        return -1

    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO interactions (timestamp, mode, query, response, action_type, pinned)
            VALUES (datetime('now', 'localtime'), ?, ?, ?, ?, ?)
        """, (mode.lower(), query.strip(), response.strip(), action_type, pinned))
        conn.commit()
        return cursor.lastrowid or -1


def get_recent(limit: int = 30) -> List[Dict[str, Any]]:
    """Retrieve the most recent interactions in reverse chronological order."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, mode, query, response, action_type, pinned
            FROM interactions
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def search_history(keyword: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Search history by keyword across queries and responses."""
    cleaned = keyword.strip()
    if not cleaned:
        return get_recent(limit)

    pattern = f"%{cleaned}%"
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, timestamp, mode, query, response, action_type, pinned
            FROM interactions
            WHERE query LIKE ? OR response LIKE ?
            ORDER BY id DESC
            LIMIT ?
        """, (pattern, pattern, limit))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def toggle_pin(interaction_id: int) -> bool:
    """Toggle pinned status of an interaction."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE interactions
            SET pinned = CASE WHEN pinned = 1 THEN 0 ELSE 1 END
            WHERE id = ?
        """, (interaction_id,))
        conn.commit()
        return cursor.rowcount > 0


def clear_history() -> bool:
    """Clear all unpinned history."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM interactions WHERE pinned = 0")
        conn.commit()
        return True
