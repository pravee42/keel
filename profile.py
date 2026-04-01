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
