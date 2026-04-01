"""SQLite-backed decision store."""

import json
import sqlite3
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path.home() / ".decisions" / "decisions.db"


@dataclass
class Decision:
    id: str
    timestamp: str
    domain: str          # code | writing | business | life | other
    title: str
    context: str         # situation / problem
    options: str         # alternatives considered
    choice: str          # what you decided
    reasoning: str       # why
    principles: str      # JSON list — extracted by LLM
    outcome: str         # filled in later via `decide outcome <id>`


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id        TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            domain    TEXT NOT NULL,
            title     TEXT NOT NULL,
            context   TEXT NOT NULL,
            options   TEXT NOT NULL,
            choice    TEXT NOT NULL,
            reasoning TEXT NOT NULL,
            principles TEXT NOT NULL DEFAULT '[]',
            outcome   TEXT NOT NULL DEFAULT ''
        )
    """)
    conn.commit()
    return conn


def save(d: Decision) -> None:
    conn = _connect()
    conn.execute(
        """INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (d.id, d.timestamp, d.domain, d.title, d.context,
         d.options, d.choice, d.reasoning, d.principles, d.outcome),
    )
    conn.commit()


def get_all() -> list[Decision]:
    conn = _connect()
    rows = conn.execute("SELECT * FROM decisions ORDER BY timestamp DESC").fetchall()
    return [Decision(**dict(r)) for r in rows]


def get_by_id(decision_id: str) -> Optional[Decision]:
    conn = _connect()
    row = conn.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,)).fetchone()
    return Decision(**dict(row)) if row else None


def update_outcome(decision_id: str, outcome: str) -> None:
    conn = _connect()
    conn.execute("UPDATE decisions SET outcome = ? WHERE id = ?", (outcome, decision_id))
    conn.commit()


def update_principles(decision_id: str, principles: list[str]) -> None:
    conn = _connect()
    conn.execute(
        "UPDATE decisions SET principles = ? WHERE id = ?",
        (json.dumps(principles), decision_id),
    )
    conn.commit()


def new_id() -> str:
    return str(uuid.uuid4())[:8]
