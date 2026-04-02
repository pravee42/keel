"""Regret Minimization Score — track deliberate vs accidental changes of mind.

For each flagged inconsistency you classify it as:
  growth  — deliberate reversal, you learned something, context changed
  regret  — accidental drift, you forgot past reasoning, you contradicted yourself

Over time this builds a personal metric: how often do you change your mind
on purpose vs by accident?
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import store
import processor as proc
import llm

DB_PATH  = Path.home() / ".keel" / "decisions.db"
DIFFS_DIR = Path.home() / ".keel" / "diffs"


# ─────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────

@dataclass
class RegretEntry:
    decision_id: str
    timestamp: str
    classification: str   # "growth" | "regret"
    note: str
    inconsistency_text: str


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS regret_scores (
            decision_id        TEXT PRIMARY KEY,
            timestamp          TEXT NOT NULL,
            classification     TEXT NOT NULL,
            note               TEXT DEFAULT '',
            inconsistency_text TEXT DEFAULT ''
        )
    """)
    conn.commit()
    return conn


# ─────────────────────────────────────────────
# Write
# ─────────────────────────────────────────────

def classify(
    decision_id: str,
    is_growth: bool,
    note: str = "",
) -> None:
    """Record your classification of a flagged inconsistency."""
    diff_text = proc.get_diff(decision_id) or ""
    classification = "growth" if is_growth else "regret"
    conn = _connect()
    conn.execute("""
        INSERT OR REPLACE INTO regret_scores
        (decision_id, timestamp, classification, note, inconsistency_text)
        VALUES (?, ?, ?, ?, ?)
    """, (
        decision_id,
        datetime.utcnow().isoformat(),
        classification,
        note,
        diff_text[:1000],
    ))
    conn.commit()


# ─────────────────────────────────────────────
# Read
# ─────────────────────────────────────────────

def get_all() -> list:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM regret_scores ORDER BY timestamp DESC"
    ).fetchall()
    return [RegretEntry(
        decision_id=r["decision_id"],
        timestamp=r["timestamp"],
        classification=r["classification"],
        note=r["note"],
        inconsistency_text=r["inconsistency_text"],
    ) for r in rows]


def get_by_id(decision_id: str) -> Optional[RegretEntry]:
    conn = _connect()
    row = conn.execute(
        "SELECT * FROM regret_scores WHERE decision_id = ?", (decision_id,)
    ).fetchone()
    if not row:
        return None
    return RegretEntry(
        decision_id=row["decision_id"],
        timestamp=row["timestamp"],
        classification=row["classification"],
        note=row["note"],
        inconsistency_text=row["inconsistency_text"],
    )


def get_pending() -> list:
    """Decisions that were flagged as contradictions but not yet classified."""
    if not DIFFS_DIR.exists():
        return []
    classified = {e.decision_id for e in get_all()}
    pending = []
    for diff_file in sorted(DIFFS_DIR.glob("*.txt"), key=lambda f: f.stat().st_mtime, reverse=True):
        decision_id = diff_file.stem
        if decision_id in classified:
            continue
        d = store.get_by_id(decision_id)
        if d:
            pending.append((d, diff_file.read_text()))
    return pending


# ─────────────────────────────────────────────
# Score
# ─────────────────────────────────────────────

def get_score() -> dict:
    """Compute the Regret Minimization Score and trend."""
    entries = get_all()
    if not entries:
        return {
            "total": 0, "growth": 0, "regret": 0,
            "score": None, "recent_score": None, "trend": None,
            "by_domain": {},
        }

    growth = sum(1 for e in entries if e.classification == "growth")
    regret_count = len(entries) - growth
    score = round(growth / len(entries), 2)

    # Trend: compare most recent 5 vs all-time
    recent = entries[:5]
    recent_growth = sum(1 for e in recent if e.classification == "growth")
    recent_score = round(recent_growth / len(recent), 2)

    if len(entries) >= 5:
        if recent_score > score + 0.1:
            trend = "improving"
        elif recent_score < score - 0.1:
            trend = "declining"
        else:
            trend = "stable"
    else:
        trend = "not enough data"

    # By domain — join with decisions table
    by_domain: dict = {}
    for e in entries:
        d = store.get_by_id(e.decision_id)
        domain = d.domain if d else "unknown"
        if domain not in by_domain:
            by_domain[domain] = {"growth": 0, "regret": 0}
        by_domain[domain][e.classification] += 1

    return {
        "total": len(entries),
        "growth": growth,
        "regret": regret_count,
        "score": score,           # 0.0 = all regret, 1.0 = all growth
        "recent_score": recent_score,
        "trend": trend,
        "by_domain": by_domain,
    }


# ─────────────────────────────────────────────
# LLM narrative
# ─────────────────────────────────────────────

_SUGGEST_PROMPT = """A developer's decision was flagged as inconsistent with their past reasoning.
Analyze it and suggest whether this is GROWTH or REGRET.

DECISION:
Title: {title}
Choice: {choice}
Reasoning: {reasoning}

FLAGGED INCONSISTENCY:
{diff_text}

Reply with ONLY valid JSON:
{{
  "growth_reason": "one sentence: why this looks like deliberate growth / learning",
  "regret_reason": "one sentence: why this looks like accidental drift / forgetting",
  "recommendation": "growth" or "regret",
  "confidence": 0.0-1.0
}}"""


def suggest_classification(d: store.Decision, diff_text: str) -> dict:
    """Ask LLM to suggest growth or regret with reasons for both."""
    import json as _json
    text = llm.complete([{"role": "user", "content": _SUGGEST_PROMPT.format(
        title=d.title,
        choice=d.choice[:200],
        reasoning=d.reasoning[:300],
        diff_text=diff_text[:800],
    )}], max_tokens=300).strip()
    try:
        return _json.loads(text)
    except Exception:
        start = text.find("{")
        if start != -1:
            try:
                obj, _ = _json.JSONDecoder().raw_decode(text, start)
                return obj
            except Exception:
                pass
    return {
        "growth_reason": "You may have updated your thinking based on new context.",
        "regret_reason": "You may have contradicted a past decision unintentionally.",
        "recommendation": "growth",
        "confidence": 0.5,
    }


_REPORT_PROMPT = """You are analyzing a developer's pattern of changing their mind.

REGRET MINIMIZATION SCORE: {score:.0%}  ({growth} growth / {regret} regret out of {total} classified)
RECENT TREND: {trend}  (recent: {recent_score:.0%} vs all-time: {score:.0%})

BY DOMAIN:
{by_domain}

CLASSIFIED DECISIONS (most recent first):
{entries}

Write a concise personal analysis (3-4 paragraphs):
1. What does this score say about how this person changes their mind?
2. Which domains show the most deliberate vs accidental drift?
3. What pattern explains the trend — are they getting better at deliberate decisions?
4. One concrete thing they should watch out for.

Be direct and specific. First person ("You tend to..."). No filler."""


def generate_report() -> Optional[str]:
    entries = get_all()
    if len(entries) < 3:
        return None

    score_data = get_score()

    by_domain_lines = "\n".join(
        f"  {domain}: {v['growth']} growth / {v['regret']} regret  "
        f"({v['growth']/(v['growth']+v['regret']):.0%} deliberate)"
        for domain, v in score_data["by_domain"].items()
    ) or "  none yet"

    entry_lines = []
    for e in entries[:20]:
        d = store.get_by_id(e.decision_id)
        title = d.title if d else e.decision_id
        symbol = "↑ growth" if e.classification == "growth" else "✗ regret"
        note = (' — "' + e.note + '"') if e.note else ""
        entry_lines.append(f"  [{e.timestamp[:10]}] {symbol}: {title}{note}")

    return llm.stream_complete([{"role": "user", "content": _REPORT_PROMPT.format(
        score=score_data["score"],
        growth=score_data["growth"],
        regret=score_data["regret"],
        total=score_data["total"],
        trend=score_data["trend"],
        recent_score=score_data["recent_score"],
        by_domain=by_domain_lines,
        entries="\n".join(entry_lines),
    )}], max_tokens=1000)
