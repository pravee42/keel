"""Synthesize a living developer identity — "who is Praveen" — from decision history.

This is the memory clone. Not a list of preferences, but a reasoning portrait:
how he thinks, what he optimizes for, what he refuses, and why.
Regenerated automatically as new decisions accumulate.
"""

import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import llm
import store
import processor as proc

PERSONA_PATH   = Path.home() / ".keel" / "persona.md"
META_PATH      = Path.home() / ".keel" / "persona_meta.json"
VERSIONS_DIR   = Path.home() / ".keel" / "personas"

# ─────────────────────────────────────────────
# Synthesis prompt
# ─────────────────────────────────────────────

PERSONA_PROMPT = """You are writing a developer identity document — a "memory clone" of a real person.

This document will be injected into AI coding assistants (Claude Code, Gemini, etc.)
so they respond in THIS PERSON'S voice, not generic best practices.
The AI should feel like a senior version of this developer sitting next to you.

FULL DECISION HISTORY ({n_decisions} decisions, {date_range}):
{history}

TOP RECURRING PRINCIPLES:
{principles}

TECH DEBT / ACTIVE COMPROMISES:
{debt}

FLAGGED INCONSISTENCIES (still unresolved):
{contradictions}

Write the identity document in this exact format:

---
# {name} — Developer Identity Profile
*Generated from {n_decisions} decisions · Last updated {today}*

## Who I Am
[3-4 sentences. Philosophy, values, how I approach software. What I care about most.]

## How I Think Through Decisions
[2-3 sentences. Fast/slow, principle-driven/pragmatic, risk tolerance, what I optimize for first]

## Architecture Principles
[Bullet list. Each: "**Principle**: why, with a concrete example from my history"]

## What I Consistently Choose
[Bullet list of specific tech/pattern choices with one-line reasons]

## What I Avoid (and Why)
[Bullet list — these are hard nos, not just preferences. Include the reason from my history]

## Active Tradeoffs I've Accepted
[Bullet list of known compromises still in place. Be honest — these are real]

## My Blind Spots (Patterns I Should Watch)
[1-3 things the decision history reveals that I should be aware of]

## How to Give Me Good Suggestions
[Instructions for the AI: what makes a suggestion land vs. get rejected.
 E.g.: "Don't suggest ORMs — I've rejected them 3 times. Always show the tradeoff explicitly."]

## Recent Focus ({recent_range})
[What I've been deciding about lately — gives the AI current context]
---

Be specific. Cite actual decisions. Make it feel like a real person wrote it, not a template.
Write in first person throughout ("I prefer...", "I avoid...", "I think...")."""


# ─────────────────────────────────────────────
# Build & save
# ─────────────────────────────────────────────

def build_persona(
    name: str = "Praveen",
    force: bool = False,
) -> Optional[str]:
    """Generate the persona doc. Returns None if not enough data yet."""
    decisions = store.get_all()
    if len(decisions) < 5:
        return None

    # Collect principles
    all_principles: list = []
    for d in decisions:
        all_principles.extend(json.loads(d.principles))
    top_principles = "\n".join(
        f"  - {p} (×{count})"
        for p, count in Counter(all_principles).most_common(20)
    )

    # Tech debt
    debt_decisions = [d for d in decisions if any(
        t in json.loads(d.tags) for t in ["pressure", "temporary", "compromise"]
    )]
    debt_text = "\n".join(
        f"  - [{d.id}] {d.title}: {d.reasoning[:150]}"
        for d in debt_decisions[:10]
    ) or "  None detected."

    # Contradictions
    contradictions = []
    for d in decisions:
        diff = proc.get_diff(d.id)
        if diff and any(w in diff.lower() for w in
                        ["inconsist", "contradict", "conflict"]):
            contradictions.append(f"  - [{d.id}] {d.title}")
    contradiction_text = "\n".join(contradictions[:5]) or "  None currently flagged."

    # Date range
    timestamps = sorted(d.timestamp for d in decisions)
    date_range = f"{timestamps[0][:10]} → {timestamps[-1][:10]}"
    recent_cutoff = datetime.utcnow() - timedelta(days=30)
    recent = [d for d in decisions
              if datetime.fromisoformat(d.timestamp) >= recent_cutoff]
    recent_text = "\n".join(
        f"  [{d.domain}] {d.title}: {d.choice[:80]}"
        for d in recent[:10]
    ) or "  No decisions in the last 30 days."

    # History (most recent 80 decisions, structured)
    history_lines = []
    for d in decisions[:80]:
        tags = json.loads(d.tags)
        history_lines.append(
            f"[{d.timestamp[:10]}] [{d.domain}] {d.title}\n"
            f"  Choice: {d.choice}\n"
            f"  Reasoning: {d.reasoning[:200]}\n"
            f"  Tags: {', '.join(tags) or 'none'}"
            + (f"\n  Outcome: {d.outcome}" if d.outcome else "")
        )

    content = llm.stream_complete(
        [{"role": "user", "content": PERSONA_PROMPT.format(
            name=name,
            n_decisions=len(decisions),
            date_range=date_range,
            history="\n\n".join(history_lines),
            principles=top_principles,
            debt=debt_text,
            contradictions=contradiction_text,
            recent_range="last 30 days",
            today=datetime.utcnow().strftime("%Y-%m-%d"),
        )}],
        max_tokens=3000,
    )

    # Snapshot current persona before overwriting
    _snapshot_current()

    # Save persona + metadata
    PERSONA_PATH.parent.mkdir(parents=True, exist_ok=True)
    PERSONA_PATH.write_text(content)

    META_PATH.write_text(json.dumps({
        "generated_at": datetime.utcnow().isoformat(),
        "n_decisions": len(decisions),
        "name": name,
    }, indent=2))

    return content


def load_persona() -> Optional[str]:
    return PERSONA_PATH.read_text() if PERSONA_PATH.exists() else None


def persona_is_stale(max_age_hours: int = 24) -> bool:
    if not META_PATH.exists():
        return True
    meta = json.loads(META_PATH.read_text())
    generated = datetime.fromisoformat(meta["generated_at"])
    return (datetime.utcnow() - generated).total_seconds() > max_age_hours * 3600


def decisions_since_last_build() -> int:
    if not META_PATH.exists():
        return len(store.get_all())
    meta = json.loads(META_PATH.read_text())
    last = datetime.fromisoformat(meta["generated_at"])
    return sum(1 for d in store.get_all()
               if datetime.fromisoformat(d.timestamp) > last)


# ─────────────────────────────────────────────
# Versioning
# ─────────────────────────────────────────────

def _snapshot_current() -> Optional[Path]:
    """Copy current persona.md to ~/.keel/personas/persona_YYYY-MM-DD.md.
    No-op if persona doesn't exist or today's snapshot already written.
    """
    if not PERSONA_PATH.exists():
        return None
    VERSIONS_DIR.mkdir(parents=True, exist_ok=True)
    date_str  = datetime.utcnow().strftime("%Y-%m-%d")
    snap_path = VERSIONS_DIR / f"persona_{date_str}.md"
    if not snap_path.exists():
        snap_path.write_text(PERSONA_PATH.read_text())
        return snap_path
    return None


def list_versions() -> list:
    """Return sorted list of version dicts: {date, path, size}."""
    if not VERSIONS_DIR.exists():
        return []
    files = sorted(VERSIONS_DIR.glob("persona_*.md"), reverse=True)
    versions = []
    for f in files:
        date_str = f.stem.replace("persona_", "")
        versions.append({
            "date": date_str,
            "path": f,
            "size": f.stat().st_size,
        })
    return versions


_DIFF_PROMPT = """You are comparing two versions of a developer's identity document.

VERSION A ({date_a}):
{text_a}

VERSION B ({date_b}):
{text_b}

Write a focused analysis of how this developer's thinking CHANGED between these two versions.
Structure:
## What shifted
[Principles, preferences, or priorities that changed — be specific, quote both versions]

## What stayed constant
[Core beliefs that held firm across both versions]

## The trajectory
[One paragraph: what direction is this person's thinking moving? Are they becoming more opinionated, more pragmatic, narrowing focus, broadening scope?]

Be concrete. If something changed, say what it was before and what it became."""


def diff_versions(date_a: Optional[str] = None, date_b: Optional[str] = None) -> Optional[str]:
    """LLM diff between two persona versions. Defaults to latest two snapshots."""
    versions = list_versions()
    # Also include current persona as the "latest"
    all_versions = []
    if PERSONA_PATH.exists():
        today = datetime.utcnow().strftime("%Y-%m-%d")
        all_versions.append({"date": today + " (current)", "path": PERSONA_PATH})
    all_versions.extend(versions)

    if len(all_versions) < 2:
        return None

    # Default: latest vs previous
    if date_a is None and date_b is None:
        v_new, v_old = all_versions[0], all_versions[1]
    else:
        # Find by date prefix
        def _find(d: str):
            for v in all_versions:
                if v["date"].startswith(d):
                    return v
            return None
        v_new = _find(date_b) if date_b else all_versions[0]
        v_old = _find(date_a) if date_a else all_versions[1]
        if not v_new or not v_old:
            return None

    return llm.stream_complete([{"role": "user", "content": _DIFF_PROMPT.format(
        date_a=v_old["date"],
        text_a=v_old["path"].read_text()[:3000],
        date_b=v_new["date"],
        text_b=v_new["path"].read_text()[:3000],
    )}], max_tokens=1200)
