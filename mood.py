"""Decision mood correlation — detect if decision quality degrades under certain conditions.

Correlates decision timestamps with:
- Time of day  (morning / afternoon / evening / late-night)
- Day of week  (weekday vs weekend)
- Reversal rate per condition (decisions that got flagged or later overridden)
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import llm
import store
import processor as proc

DIFFS_PATH = Path.home() / ".decisions" / "diffs"
RESOLUTIONS_PATH = Path.home() / ".decisions" / "resolutions.jsonl"


# ─────────────────────────────────────────────
# Time bucketing
# ─────────────────────────────────────────────

def time_bucket(timestamp: str) -> str:
    """Bucket a UTC ISO timestamp into a named time-of-day slot."""
    hour = datetime.fromisoformat(timestamp).hour
    if 5 <= hour < 9:   return "early-morning (5–9am)"
    if 9 <= hour < 12:  return "morning (9am–12pm)"
    if 12 <= hour < 14: return "midday (12–2pm)"
    if 14 <= hour < 18: return "afternoon (2–6pm)"
    if 18 <= hour < 21: return "evening (6–9pm)"
    if 21 <= hour < 24: return "late-night (9pm–12am)"
    return "night (12–5am)"


def day_type(timestamp: str) -> str:
    dt = datetime.fromisoformat(timestamp)
    return "weekend" if dt.weekday() >= 5 else "weekday"


def day_name(timestamp: str) -> str:
    return datetime.fromisoformat(timestamp).strftime("%A")


# ─────────────────────────────────────────────
# Decision quality signal
# ─────────────────────────────────────────────

def _get_resolutions() -> set[str]:
    if not RESOLUTIONS_PATH.exists():
        return set()
    ids = set()
    for line in RESOLUTIONS_PATH.read_text().strip().split("\n"):
        if line.strip():
            ids.add(json.loads(line)["decision_id"])
    return ids


def was_flagged(decision_id: str) -> bool:
    diff = proc.get_diff(decision_id)
    if not diff:
        return False
    return any(w in diff.lower() for w in
               ["inconsist", "contradict", "conflict", "however", "but previously"])


def quality_label(d: store.Decision, resolutions: set[str]) -> str:
    """consistent | flagged | reversed"""
    if d.id in resolutions:
        return "reversed"
    if was_flagged(d.id):
        return "flagged"
    return "consistent"


# ─────────────────────────────────────────────
# Correlation analysis
# ─────────────────────────────────────────────

def build_correlation_data(decisions: list[store.Decision]) -> dict:
    """Aggregate decision quality by time-of-day, day-of-week, and day-name."""
    resolutions = _get_resolutions()

    by_time  = defaultdict(lambda: {"total": 0, "flagged": 0, "reversed": 0, "decisions": []})
    by_day   = defaultdict(lambda: {"total": 0, "flagged": 0, "reversed": 0, "decisions": []})
    by_dname = defaultdict(lambda: {"total": 0, "flagged": 0, "reversed": 0, "decisions": []})

    for d in decisions:
        label  = quality_label(d, resolutions)
        bucket = time_bucket(d.timestamp)
        dtype  = day_type(d.timestamp)
        dname  = day_name(d.timestamp)

        for store_dict in (by_time[bucket], by_day[dtype], by_dname[dname]):
            store_dict["total"] += 1
            if label in ("flagged", "reversed"):
                store_dict["flagged"] += 1
            if label == "reversed":
                store_dict["reversed"] += 1
            store_dict["decisions"].append({"id": d.id, "title": d.title, "quality": label})

    return {
        "by_time":  dict(by_time),
        "by_day":   dict(by_day),
        "by_dname": dict(by_dname),
    }


def reversal_rate(bucket_data: dict) -> float:
    total = bucket_data["total"]
    return round(bucket_data["flagged"] / total, 2) if total > 0 else 0.0


def find_worst_conditions(corr: dict) -> list[tuple[str, str, float]]:
    """Returns list of (dimension, condition, rate) sorted by flagged rate, worst first."""
    results = []
    for dim, buckets in corr.items():
        for name, data in buckets.items():
            if data["total"] >= 2:  # need at least 2 to be meaningful
                rate = reversal_rate(data)
                if rate > 0:
                    results.append((dim, name, rate, data["total"]))
    results.sort(key=lambda x: x[2], reverse=True)
    return results


# ─────────────────────────────────────────────
# LLM narrative
# ─────────────────────────────────────────────

MOOD_PROMPT = """Analyze this person's decision quality across different conditions.
Write a concise, specific insight report — like a data analyst reviewing someone's patterns.

DATA:
{data_summary}

WORST CONDITIONS (highest flagged/reversal rate):
{worst}

Write:
1. **Key finding** — one sharp sentence about their most notable degradation pattern
2. **Time patterns** — when are their decisions most/least reliable?
3. **Day patterns** — any weekday vs weekend differences?
4. **Watch out for** — specific conditions where they should slow down and double-check
5. **When they're sharpest** — conditions with zero flags

Be specific with numbers. Use the decision titles as examples. Max 300 words."""


def generate_mood_report(decisions: list[store.Decision]) -> Optional[str]:
    if len(decisions) < 3:
        return None

    corr = build_correlation_data(decisions)
    worst = find_worst_conditions(corr)

    # Build summary table
    lines = []
    for bucket, data in sorted(corr["by_time"].items()):
        rate = reversal_rate(data)
        flag = "⚠" if rate > 0.3 else ("✓" if rate == 0 else "·")
        examples = ", ".join(d["title"] for d in data["decisions"][:2])
        lines.append(f"  {flag} {bucket}: {data['total']} decisions, {rate:.0%} flagged — e.g. {examples}")

    for bucket, data in sorted(corr["by_day"].items()):
        rate = reversal_rate(data)
        lines.append(f"  {bucket}: {data['total']} decisions, {rate:.0%} flagged")

    worst_lines = "\n".join(
        f"  {cond} ({dim.replace('by_', '')}): {rate:.0%} flag rate across {total} decisions"
        for dim, cond, rate, total in worst[:5]
    ) or "  None detected yet."

    prompt = MOOD_PROMPT.format(
        data_summary="\n".join(lines),
        worst=worst_lines,
    )
    return llm.stream_complete([{"role": "user", "content": prompt}], max_tokens=1024)


# ─────────────────────────────────────────────
# Quick stats (no LLM needed)
# ─────────────────────────────────────────────

def quick_stats(decisions: list[store.Decision]) -> dict:
    """Fast stats table — no LLM call."""
    corr = build_correlation_data(decisions)
    rows = []
    for bucket, data in corr["by_time"].items():
        if data["total"] > 0:
            rows.append({
                "condition": bucket,
                "total": data["total"],
                "flagged": data["flagged"],
                "rate": reversal_rate(data),
            })
    rows.sort(key=lambda r: r["rate"], reverse=True)

    worst = find_worst_conditions(corr)
    return {
        "time_rows": rows,
        "day_rows": [
            {"condition": k, "total": v["total"],
             "flagged": v["flagged"], "rate": reversal_rate(v)}
            for k, v in corr["by_day"].items()
        ],
        "worst": worst[:3],
        "total_decisions": len(decisions),
        "total_flagged": sum(1 for d in decisions if was_flagged(d.id)),
    }
