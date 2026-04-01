"""SQLite-backed decision store."""

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

DB_PATH = Path.home() / ".keel" / "decisions.db"


@dataclass
class Decision:
    id: str
    timestamp: str
    domain: str       # code | writing | business | life | other
    title: str
    context: str      # situation / problem
    options: str      # alternatives considered
    choice: str       # what you decided
    reasoning: str    # why
    principles: str   # JSON list — extracted by LLM
    outcome: str      # filled in later
    tags: str         # JSON list — pressure | uncertainty | compromise | temporary | arch
    paths: str        # JSON list — file/module paths this decision touches
    project: str      # absolute git root path, or '' if unknown


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id         TEXT PRIMARY KEY,
            timestamp  TEXT NOT NULL,
            domain     TEXT NOT NULL,
            title      TEXT NOT NULL,
            context    TEXT NOT NULL,
            options    TEXT NOT NULL,
            choice     TEXT NOT NULL,
            reasoning  TEXT NOT NULL,
            principles TEXT NOT NULL DEFAULT '[]',
            outcome    TEXT NOT NULL DEFAULT '',
            tags       TEXT NOT NULL DEFAULT '[]',
            paths      TEXT NOT NULL DEFAULT '[]',
            project    TEXT NOT NULL DEFAULT ''
        )
    """)
    _migrate(conn)
    conn.commit()
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    existing = {row[1] for row in conn.execute("PRAGMA table_info(decisions)").fetchall()}
    if "tags" not in existing:
        conn.execute("ALTER TABLE decisions ADD COLUMN tags TEXT NOT NULL DEFAULT '[]'")
    if "paths" not in existing:
        conn.execute("ALTER TABLE decisions ADD COLUMN paths TEXT NOT NULL DEFAULT '[]'")
    if "project" not in existing:
        conn.execute("ALTER TABLE decisions ADD COLUMN project TEXT NOT NULL DEFAULT ''")


def save(d: Decision) -> None:
    conn = _connect()
    conn.execute(
        "INSERT INTO decisions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (d.id, d.timestamp, d.domain, d.title, d.context,
         d.options, d.choice, d.reasoning, d.principles, d.outcome,
         d.tags, d.paths, d.project),
    )
    conn.commit()


def get_all() -> list:
    conn = _connect()
    rows = conn.execute("SELECT * FROM decisions ORDER BY timestamp DESC").fetchall()
    return [_row_to_decision(r) for r in rows]


def get_by_id(decision_id: str) -> Optional[Decision]:
    conn = _connect()
    row = conn.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,)).fetchone()
    return _row_to_decision(row) if row else None


def get_by_path(path_fragment: str) -> list:
    """Find decisions that touch a given file path."""
    all_d = get_all()
    return [d for d in all_d if path_fragment in d.paths]


def get_by_tag(tag: str) -> list:
    all_d = get_all()
    return [d for d in all_d if tag in json.loads(d.tags)]


def get_by_project(project_root: str) -> list:
    """Return all decisions made in a specific git repo, newest first."""
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM decisions WHERE project = ? ORDER BY timestamp DESC",
        (project_root,)
    ).fetchall()
    return [_row_to_decision(r) for r in rows]


def get_projects() -> list:
    """Return all known project roots with decision counts and latest timestamp."""
    conn = _connect()
    rows = conn.execute("""
        SELECT project, COUNT(*) as count, MAX(timestamp) as latest
        FROM decisions
        WHERE project != ''
        GROUP BY project
        ORDER BY latest DESC
    """).fetchall()
    return [{"project": r["project"], "count": r["count"], "latest": r["latest"]}
            for r in rows]


def get_decisions_since(timestamp: str, project: Optional[str] = None) -> list:
    """Return decisions newer than the given ISO timestamp, optionally filtered by project."""
    conn = _connect()
    if project:
        rows = conn.execute(
            "SELECT * FROM decisions WHERE timestamp > ? AND project = ? ORDER BY timestamp DESC",
            (timestamp, project)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM decisions WHERE timestamp > ? ORDER BY timestamp DESC",
            (timestamp,)
        ).fetchall()
    return [_row_to_decision(r) for r in rows]


def update_outcome(decision_id: str, outcome: str) -> None:
    conn = _connect()
    conn.execute("UPDATE decisions SET outcome = ? WHERE id = ?", (outcome, decision_id))
    conn.commit()


def update_principles(decision_id: str, principles: list) -> None:
    conn = _connect()
    conn.execute("UPDATE decisions SET principles = ? WHERE id = ?",
                 (json.dumps(principles), decision_id))
    conn.commit()


def update_tags(decision_id: str, tags: list) -> None:
    conn = _connect()
    conn.execute("UPDATE decisions SET tags = ? WHERE id = ?",
                 (json.dumps(tags), decision_id))
    conn.commit()


def update_paths(decision_id: str, paths: list) -> None:
    conn = _connect()
    conn.execute("UPDATE decisions SET paths = ? WHERE id = ?",
                 (json.dumps(paths), decision_id))
    conn.commit()


def delete(decision_id: str) -> bool:
    """Permanently delete a decision. Returns True if a row was removed."""
    conn = _connect()
    cursor = conn.execute("DELETE FROM decisions WHERE id = ?", (decision_id,))
    conn.commit()
    return cursor.rowcount > 0


def update_decision(d: Decision) -> None:
    """Overwrite all editable fields of an existing decision."""
    conn = _connect()
    conn.execute("""
        UPDATE decisions
        SET domain=?, title=?, context=?, options=?, choice=?, reasoning=?
        WHERE id=?
    """, (d.domain, d.title, d.context, d.options, d.choice, d.reasoning, d.id))
    conn.commit()


def _row_to_decision(row) -> Decision:
    d = dict(row)
    d.setdefault("tags", "[]")
    d.setdefault("paths", "[]")
    d.setdefault("project", "")
    return Decision(**d)


def new_id() -> str:
    return str(uuid.uuid4())[:8]
