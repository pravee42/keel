"""Tech debt classifier — surface decisions made under pressure or with uncertainty."""

import json
from datetime import datetime
from typing import Optional

import llm
import store
import processor as proc

DEBT_PROMPT = """Analyze these tech debt decisions and produce a prioritized list.
Each decision was made under pressure, uncertainty, or as an acknowledged compromise.

DECISIONS:
{decisions_text}

For each, assess:
- **Impact**: how broad is the blast radius if this bites you?
- **Age**: older unresolved debt is higher risk
- **Outcome signal**: if outcome was recorded and negative, boost priority

Output a ranked list from highest to lowest priority. Format each as:
### [rank]. [title]
**Decision ID**: <id>  |  **Date**: <date>  |  **Tags**: <tags>
**Why it's debt**: <one sentence>
**Risk**: <what could go wrong>
**Suggested action**: <pay it off | monitor | accept it>

End with:
---
**Bottom line**: <one sentence summary of the overall debt picture>"""


def get_debt_decisions(
    domain: Optional[str] = None,
    include_tags: Optional[list] = None,
) -> list[store.Decision]:
    """Return decisions tagged as debt candidates."""
    debt_tags = include_tags or ["pressure", "uncertainty", "compromise", "temporary"]
    all_d = store.get_all()

    results = []
    for d in all_d:
        tags = json.loads(d.tags)
        if any(t in tags for t in debt_tags):
            if domain is None or d.domain == domain:
                results.append(d)
    return results


def score_debt(d: store.Decision) -> float:
    """Rough priority score — higher = more urgent."""
    score = 0.0
    tags  = json.loads(d.tags)

    # Tag weight
    if "pressure"    in tags: score += 2.0
    if "temporary"   in tags: score += 3.0
    if "compromise"  in tags: score += 1.5
    if "uncertainty" in tags: score += 1.0
    if "arch"        in tags: score += 2.0  # arch debt is higher impact

    # Age: older unresolved = more urgent
    try:
        age_days = (datetime.utcnow() - datetime.fromisoformat(d.timestamp)).days
        score += min(age_days / 30, 5.0)   # cap at 5 points for age
    except Exception:
        pass

    # Flagged consistency = extra risk signal
    if proc.get_diff(d.id):
        score += 2.0

    # Negative outcome = already bit us
    if d.outcome and any(w in d.outcome.lower() for w in
                         ["fail", "broke", "regret", "wrong", "bad", "problem"]):
        score += 3.0

    return round(score, 1)


def generate_debt_report(decisions: list[store.Decision]) -> str:
    if not decisions:
        return "No tech debt decisions found. Either you're squeaky clean or nothing is tagged yet."

    # Sort by score
    scored = sorted(decisions, key=score_debt, reverse=True)

    decisions_text = "\n\n".join(
        f"[{d.id}] {d.title}\n"
        f"Date: {d.timestamp[:10]} | Domain: {d.domain} | Tags: {', '.join(json.loads(d.tags))}\n"
        f"Context: {d.context[:200]}\n"
        f"Choice: {d.choice}\n"
        f"Reasoning: {d.reasoning[:300]}\n"
        f"Outcome: {d.outcome or 'not recorded'}\n"
        f"Debt score: {score_debt(d)}"
        for d in scored[:20]
    )

    return llm.stream_complete(
        [{"role": "user", "content": DEBT_PROMPT.format(decisions_text=decisions_text)}],
        max_tokens=2048,
    )


def quick_debt_table(decisions: list[store.Decision]) -> list[dict]:
    """Fast table — no LLM needed."""
    scored = sorted(decisions, key=score_debt, reverse=True)
    return [
        {
            "id":     d.id,
            "title":  d.title,
            "domain": d.domain,
            "date":   d.timestamp[:10],
            "tags":   json.loads(d.tags),
            "score":  score_debt(d),
            "has_outcome": bool(d.outcome),
        }
        for d in scored
    ]
