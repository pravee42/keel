"""Token usage tracking and cost visibility for keel LLM calls."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

USAGE_LOG = Path.home() / ".keel" / "usage.jsonl"

# Prices per million tokens: (input $/1M, output $/1M)
PRICES: dict = {
    "claude-opus-4-6":              (5.00,  25.00),
    "claude-sonnet-4-6":            (3.00,  15.00),
    "claude-haiku-4-5":             (1.00,   5.00),
    "claude-haiku-4-5-20251001":    (1.00,   5.00),
    "gpt-4o":                       (2.50,  10.00),
    "gpt-4o-mini":                  (0.15,   0.60),
    "o3-mini":                      (1.10,   4.40),
    "gemini-2.0-flash":             (0.075,  0.30),
    "gemini-2.5-pro-preview-05-06": (1.25,  10.00),
    "gemini-1.5-pro":               (1.25,   5.00),
    "mistral-large-latest":         (2.00,   6.00),
    "mistral-medium-latest":        (0.40,   1.20),
    "mistral-small-latest":         (0.10,   0.30),
    "codestral-latest":             (0.20,   0.60),
}

_FALLBACK_PRICE = (3.00, 15.00)   # unknown model → assume sonnet-level


def log_usage(
    model: str,
    provider: str,
    input_tokens: int,
    output_tokens: int,
    command: str = "",
) -> None:
    """Append one usage record to ~/.keel/usage.jsonl. Never raises."""
    try:
        USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts":      datetime.utcnow().isoformat(),
            "provider": provider,
            "model":    model,
            "in":       input_tokens,
            "out":      output_tokens,
            "cmd":      command,
        }
        with open(USAGE_LOG, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


def calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate USD cost for a single call."""
    base = model.split("/")[-1]  # strip openrouter prefix e.g. "anthropic/claude-opus-4-6"
    p = PRICES.get(base) or PRICES.get(model, _FALLBACK_PRICE)
    return (input_tokens * p[0] + output_tokens * p[1]) / 1_000_000


def get_summary(since_days: int = 30) -> dict:
    """Load usage log and compute totals, broken down by model and by day."""
    if not USAGE_LOG.exists():
        return {"records": [], "total_cost": 0.0,
                "total_input": 0, "total_output": 0,
                "by_model": {}, "by_day": {}}

    cutoff = (datetime.utcnow() - timedelta(days=since_days)).isoformat()

    records = []
    for line in USAGE_LOG.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            if r.get("ts", r.get("timestamp", "")) >= cutoff:
                # Normalise old key names
                r.setdefault("in",  r.pop("input_tokens",  0))
                r.setdefault("out", r.pop("output_tokens", 0))
                r.setdefault("ts",  r.pop("timestamp", ""))
                r.setdefault("cmd", r.pop("command", ""))
                records.append(r)
        except Exception:
            pass

    by_model: dict = {}
    by_day:   dict = {}
    total_cost   = 0.0
    total_input  = 0
    total_output = 0

    for r in records:
        m    = r.get("model", "unknown")
        inp  = r.get("in",  0)
        out  = r.get("out", 0)
        cost = calc_cost(m, inp, out)
        day  = r.get("ts", "")[:10]

        total_cost   += cost
        total_input  += inp
        total_output += out

        if m not in by_model:
            by_model[m] = {"calls": 0, "input": 0, "output": 0, "cost": 0.0}
        by_model[m]["calls"] += 1
        by_model[m]["input"] += inp
        by_model[m]["output"] += out
        by_model[m]["cost"]  += cost

        if day not in by_day:
            by_day[day] = {"calls": 0, "cost": 0.0}
        by_day[day]["calls"] += 1
        by_day[day]["cost"]  += cost

    return {
        "records":      records,
        "total_cost":   round(total_cost,   6),
        "total_input":  total_input,
        "total_output": total_output,
        "by_model":     by_model,
        "by_day":       dict(sorted(by_day.items())),
    }
