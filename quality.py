"""Decision quality correlation — which principles lead to good outcomes?"""

import json
from typing import Optional

import store
import llm

VALID_QUALITIES = ("good", "neutral", "bad")


_CORRELATION_PROMPT = """You are analyzing a developer's decision outcomes to identify which
reasoning principles lead to good results and which lead to bad ones.

DECISIONS WITH OUTCOMES (format: quality | title | principles | outcome):
{entries}

Analyze this data and write a concise report (3-4 paragraphs):
1. Which principles appear most often in GOOD outcomes? What do they have in common?
2. Which principles appear most often in BAD outcomes? What pattern explains the failures?
3. What specific advice should this person act on based on this data?
4. One principle they should stop trusting and one they should lean into more.

Be direct and specific. Use first person ("You tend to..."). Cite specific decisions."""


def get_principle_stats() -> dict:
    """Count how often each principle appears in good vs bad outcomes."""
    decisions = store.get_with_outcomes()
    stats: dict = {}

    for d in decisions:
        principles = json.loads(d.principles) if d.principles else []
        q = d.outcome_quality
        for p in principles:
            if p not in stats:
                stats[p] = {"good": 0, "neutral": 0, "bad": 0, "total": 0}
            stats[p][q] += 1
            stats[p]["total"] += 1

    # Sort by total frequency descending
    return dict(sorted(stats.items(), key=lambda x: x[1]["total"], reverse=True))


def generate_quality_report() -> Optional[str]:
    """LLM analysis: which principles produce good vs bad outcomes."""
    decisions = store.get_with_outcomes()
    if len(decisions) < 3:
        return None

    lines = []
    for d in decisions[:30]:
        principles = json.loads(d.principles) if d.principles else []
        p_str = ", ".join(principles[:4]) if principles else "none"
        lines.append(
            f"{d.outcome_quality.upper()} | {d.title} | "
            f"[{p_str}] | {d.outcome[:120]}"
        )

    return llm.stream_complete([{"role": "user", "content": _CORRELATION_PROMPT.format(
        entries="\n".join(lines),
    )}], max_tokens=900)


def quick_stats(decisions: Optional[list] = None) -> dict:
    """Return summary counts for quick display."""
    if decisions is None:
        decisions = store.get_with_outcomes()

    total   = len(decisions)
    good    = sum(1 for d in decisions if d.outcome_quality == "good")
    neutral = sum(1 for d in decisions if d.outcome_quality == "neutral")
    bad     = sum(1 for d in decisions if d.outcome_quality == "bad")

    return {
        "total":   total,
        "good":    good,
        "neutral": neutral,
        "bad":     bad,
        "rate":    round(good / total, 2) if total else None,
    }
