"""Weekly digest — categorize decisions, surface patterns, flag unresolved contradictions."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import llm
import store
import processor as proc

DIGESTS_PATH = Path.home() / ".keel" / "digests"
RESOLUTIONS_PATH = Path.home() / ".keel" / "resolutions.jsonl"


# ─────────────────────────────────────────────
# Resolution tracking (user can mark a contradiction as intentional)
# ─────────────────────────────────────────────

def mark_resolved(decision_id: str, reason: str):
    """Mark a flagged contradiction as a deliberate reversal with a reason."""
    RESOLUTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "decision_id": decision_id,
        "reason": reason,
        "resolved_at": datetime.utcnow().isoformat(),
    }
    with open(RESOLUTIONS_PATH, "a") as f:
        f.write(json.dumps(entry) + "\n")


def get_resolutions() -> dict[str, str]:
    """Returns {decision_id: reason} for all resolved contradictions."""
    if not RESOLUTIONS_PATH.exists():
        return {}
    resolutions = {}
    for line in RESOLUTIONS_PATH.read_text().strip().split("\n"):
        if line.strip():
            r = json.loads(line)
            resolutions[r["decision_id"]] = r["reason"]
    return resolutions


# ─────────────────────────────────────────────
# Categorization
# ─────────────────────────────────────────────

def categorize_decisions(decisions: list[store.Decision]) -> dict:
    """Split decisions into: consistent / deliberate_reversal / contradiction / new_territory."""
    resolutions = get_resolutions()

    consistent = []
    deliberate_reversals = []
    contradictions = []
    new_territory = []

    for d in decisions:
        diff = proc.get_diff(d.id)

        if diff is None:
            new_territory.append(d)
        elif d.id in resolutions:
            deliberate_reversals.append((d, resolutions[d.id]))
        else:
            # Check if the diff actually flagged an inconsistency
            flagged = any(w in diff.lower() for w in
                         ["inconsist", "contradict", "conflict", "however", "but previously"])
            if flagged:
                contradictions.append((d, diff))
            else:
                consistent.append(d)

    return {
        "consistent": consistent,
        "deliberate_reversals": deliberate_reversals,
        "contradictions": contradictions,
        "new_territory": new_territory,
    }


# ─────────────────────────────────────────────
# Narrative generation
# ─────────────────────────────────────────────

DIGEST_PROMPT = """You are writing a weekly thinking digest for someone who tracks their decisions.
Write in second person ("you"), concise, insightful — like a thoughtful colleague who's been watching.

DATA:
Period: {period}
Total decisions: {total}

CONSISTENT DECISIONS ({n_consistent}):
{consistent_text}

DELIBERATE REVERSALS ({n_reversals}) — user marked these as intentional:
{reversals_text}

UNRESOLVED CONTRADICTIONS ({n_contradictions}):
{contradictions_text}

NEW TERRITORY ({n_new}) — no past patterns to compare:
{new_text}

Write a digest with these sections:
1. **This week** — 2-3 sentence overview of what you were deciding about
2. **Patterns holding** — what principles you're consistently applying (cite specifics)
3. **Worth examining** — the unresolved contradictions, what the tension actually is
4. **One question** — a single reflective question based on this week's decisions

Keep it under 400 words. No bullet points in the overview. Be specific, not generic."""


def generate_narrative(categorized: dict, period: str) -> str:
    total = sum(
        len(v) if isinstance(v[0] if v else None, store.Decision) else len(v)
        for v in categorized.values()
    )

    def fmt_decisions(items) -> str:
        if not items:
            return "None"
        result = []
        for item in items:
            if isinstance(item, store.Decision):
                result.append(f"- [{item.id}] {item.title}: {item.reasoning[:150]}")
            elif isinstance(item, tuple) and len(item) == 2:
                d, extra = item
                result.append(f"- [{d.id}] {d.title}: {d.reasoning[:150]}\n  Note: {str(extra)[:200]}")
        return "\n".join(result) or "None"

    prompt = DIGEST_PROMPT.format(
        period=period,
        total=total,
        n_consistent=len(categorized["consistent"]),
        consistent_text=fmt_decisions(categorized["consistent"]),
        n_reversals=len(categorized["deliberate_reversals"]),
        reversals_text=fmt_decisions(categorized["deliberate_reversals"]),
        n_contradictions=len(categorized["contradictions"]),
        contradictions_text=fmt_decisions(categorized["contradictions"]),
        n_new=len(categorized["new_territory"]),
        new_text=fmt_decisions(categorized["new_territory"]),
    )

    return llm.stream_complete([{"role": "user", "content": prompt}], max_tokens=1024)


# ─────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────

def build_digest(days: int = 7) -> Optional[dict]:
    since = datetime.utcnow() - timedelta(days=days)
    all_decisions = store.get_all()
    recent = [d for d in all_decisions if datetime.fromisoformat(d.timestamp) >= since]

    if not recent:
        return None

    period = f"{since.strftime('%b %d')} – {datetime.utcnow().strftime('%b %d, %Y')}"
    categorized = categorize_decisions(recent)
    narrative = generate_narrative(categorized, period)

    digest = {
        "period": period,
        "generated_at": datetime.utcnow().isoformat(),
        "days": days,
        "stats": {
            "total": len(recent),
            "consistent": len(categorized["consistent"]),
            "deliberate_reversals": len(categorized["deliberate_reversals"]),
            "contradictions": len(categorized["contradictions"]),
            "new_territory": len(categorized["new_territory"]),
        },
        "categorized": {
            k: [d.id if isinstance(d, store.Decision) else d[0].id for d in v]
            for k, v in categorized.items()
        },
        "narrative": narrative,
    }

    # Save to disk
    DIGESTS_PATH.mkdir(parents=True, exist_ok=True)
    filename = DIGESTS_PATH / f"{datetime.utcnow().strftime('%Y-%m-%d')}.json"
    filename.write_text(json.dumps(digest, indent=2))

    return digest
