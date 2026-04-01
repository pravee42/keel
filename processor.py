"""Process queue events: classify → extract decision → consistency check → notify."""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional

import llm
import store
import analyzer

QUEUE_PATH = Path.home() / ".decisions" / "queue.jsonl"
PROCESSED_PATH = Path.home() / ".decisions" / "processed.jsonl"


# ─────────────────────────────────────────────
# Step 1: Classify — is this a decision worth tracking?
# ─────────────────────────────────────────────

CLASSIFIER_PROMPT = """You are filtering events to find architectural, design, or strategic decisions.

An event is worth tracking if it contains:
- A choice between approaches/tools/frameworks/architectures
- A tradeoff being made (speed vs quality, simplicity vs flexibility, etc.)
- A strategic direction being set (what to build, how to structure, what to prioritize)
- An explicit reasoning about WHY something is done a certain way

NOT worth tracking:
- Routine tasks ("fix typo", "add test", "update README")
- Questions or exploration without a decision
- Debugging a specific bug
- Formatting/style changes
- "How do I..." questions

Source: {source}
Type: {type}
Content:
{text}

Reply with ONLY valid JSON:
{{"is_decision": true/false, "confidence": 0.0-1.0, "reason": "one line why"}}"""


def classify(event: dict) -> dict:
    text = llm.complete([{"role": "user", "content": CLASSIFIER_PROMPT.format(
        source=event["source"],
        type=event["type"],
        text=event["text"][:2000],
    )}], max_tokens=256).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end]) if start != -1 else {"is_decision": False, "confidence": 0}


# ─────────────────────────────────────────────
# Step 2: Extract structured decision from raw text
# ─────────────────────────────────────────────

EXTRACTOR_PROMPT = """Extract a structured decision from this {source} {type}.

Content:
{text}

Reply with ONLY valid JSON (no markdown):
{{
  "title": "short title (under 10 words)",
  "domain": "code|writing|business|life|other",
  "context": "what situation/problem prompted this",
  "options": "what alternatives were considered or implied",
  "choice": "what was decided or what approach was taken",
  "reasoning": "why — extract the explicit or implied reasoning"
}}"""


def extract_decision(event: dict) -> dict:
    text = llm.complete([{"role": "user", "content": EXTRACTOR_PROMPT.format(
        source=event["source"],
        type=event["type"],
        text=event["text"][:3000],
    )}], max_tokens=1024).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])


# ─────────────────────────────────────────────
# Step 3: Notify user
# ─────────────────────────────────────────────

def notify(title: str, message: str):
    """macOS notification. Silently fails on other platforms."""
    try:
        script = f'display notification "{message[:200]}" with title "decide: {title}"'
        subprocess.run(["osascript", "-e", script], capture_output=True, timeout=3)
    except Exception:
        pass


def notify_inconsistency(decision_title: str, diff_summary: str):
    """Extract first sentence of diff for notification."""
    first_line = diff_summary.split("\n")[0][:150]
    notify(f"⚠ {decision_title}", first_line)


# ─────────────────────────────────────────────
# Main processing loop
# ─────────────────────────────────────────────

def process_queue(verbose: bool = False, limit: int = 50):
    """Process unprocessed events from queue. Called by `decide process` or cron."""
    if not QUEUE_PATH.exists():
        if verbose:
            print("Queue is empty.")
        return

    lines = QUEUE_PATH.read_text().strip().split("\n")
    events = [json.loads(l) for l in lines if l.strip()]
    pending = [e for e in events if not e.get("processed")]

    if not pending:
        if verbose:
            print("Nothing to process.")
        return

    # Process up to `limit` events
    to_process = pending[:limit]
    if verbose:
        print(f"Processing {len(to_process)} events...")

    results = []
    for event in to_process:
        result = _process_one(event, verbose=verbose)
        results.append(result)
        event["processed"] = True

    # Rewrite queue with updated processed flags
    all_events = {e["id"]: e for e in events}
    for e in to_process:
        all_events[e["id"]] = e

    with open(QUEUE_PATH, "w") as f:
        for e in all_events.values():
            f.write(json.dumps(e) + "\n")

    return results


_PRESSURE_SIGNALS = [
    "deadline", "asap", "quick", "fast", "temporary", "for now", "hack",
    "workaround", "just ship", "mvp", "good enough", "later", "todo",
    "tech debt", "revisit", "short-term",
]
_UNCERTAINTY_SIGNALS = [
    "not sure", "maybe", "unsure", "might", "could be", "possibly",
    "experiment", "try", "test", "see if", "not certain", "unclear",
]
_ARCH_SIGNALS = [
    "architecture", "schema", "database", "auth", "api", "service",
    "framework", "library", "pattern", "structure", "design", "migrate",
    "refactor", "rewrite", "split", "merge", "monolith", "microservice",
]


def _detect_tags(text: str, extracted: dict) -> list:
    combined = (text + " " + extracted.get("reasoning", "")).lower()
    tags = []
    if any(s in combined for s in _PRESSURE_SIGNALS):
        tags.append("pressure")
    if any(s in combined for s in _UNCERTAINTY_SIGNALS):
        tags.append("uncertainty")
    if any(s in combined for s in _ARCH_SIGNALS):
        tags.append("arch")
    if "compromise" in combined or "tradeoff" in combined or "trade-off" in combined:
        tags.append("compromise")
    if "temporary" in combined or "for now" in combined:
        tags.append("temporary")
    return tags


def _detect_paths(event: dict) -> list:
    """Extract file paths from git commit text or prompt."""
    import re
    text = event.get("text", "")
    # Match common path patterns: src/foo/bar.py, ./lib/utils.ts, etc.
    paths = re.findall(r'(?:^|\s)((?:\./|src/|lib/|app/|pkg/|internal/)[\w/.-]+\.\w+)', text)
    # Also grab paths from git diff stat lines: "  src/auth/jwt.py | 12 ++"
    paths += re.findall(r'^\s+([\w/.-]+\.\w+)\s+\|', text, re.MULTILINE)
    return list(set(p.strip() for p in paths))[:20]


def _process_one(event: dict, verbose: bool = False) -> dict:
    """Classify, extract, store, and check one event."""
    if verbose:
        source = event["source"]
        preview = event["text"][:60].replace("\n", " ")
        print(f"  [{source}] {preview}...")

    # Step 1: Classify
    classification = classify(event)
    if not classification.get("is_decision") or classification.get("confidence", 0) < 0.6:
        if verbose:
            print(f"    → skipped ({classification.get('reason', 'not a decision')})")
        return {"skipped": True, "reason": classification.get("reason")}

    # Step 2: Extract structured decision
    try:
        extracted = extract_decision(event)
    except Exception as e:
        if verbose:
            print(f"    → extraction failed: {e}")
        return {"skipped": True, "reason": f"extraction error: {e}"}

    def _s(val, default="") -> str:
        """Coerce LLM output field to str — guards against null/list returns."""
        if val is None:
            return default
        if isinstance(val, list):
            return ", ".join(str(v) for v in val)
        return str(val)

    # Step 3: Build and store Decision
    d = store.Decision(
        id=store.new_id(),
        timestamp=event["timestamp"],
        domain=_s(extracted.get("domain"), "other"),
        title=_s(extracted.get("title"), "Untitled"),
        context=_s(extracted.get("context")),
        options=_s(extracted.get("options")),
        choice=_s(extracted.get("choice")),
        reasoning=_s(extracted.get("reasoning")),
        principles="[]",
        outcome="",
        tags=json.dumps(_detect_tags(event["text"], extracted)),
        paths=json.dumps(_detect_paths(event)),
    )

    # Extract principles
    try:
        principles = analyzer.extract_principles(d)
        d.principles = json.dumps(principles)
    except Exception:
        pass

    store.save(d)

    if verbose:
        print(f"    → saved [{d.id}]: {d.title}")
        if json.loads(d.principles):
            print(f"       principles: {', '.join(json.loads(d.principles))}")

    # Step 4: Consistency check
    history = [h for h in store.get_all() if h.id != d.id]
    if history:
        try:
            similar = analyzer.find_similar(d, history, top_n=2)
            if similar:
                diff = analyzer.consistency_diff(d, similar)
                # Check if inconsistency was flagged
                flagged = any(w in diff.lower() for w in
                              ["inconsist", "contradict", "conflict", "changed", "different from"])
                if flagged:
                    notify_inconsistency(d.title, diff)
                    if verbose:
                        print(f"    ⚠ Inconsistency flagged — check `decide show {d.id}`")
                    # Store diff alongside decision in a sidecar file
                    _save_diff(d.id, diff)
        except Exception as e:
            if verbose:
                print(f"    → consistency check failed: {e}")

    return {"saved": True, "id": d.id, "title": d.title}


def _save_diff(decision_id: str, diff: str):
    """Save consistency diff to sidecar file."""
    diffs_path = Path.home() / ".decisions" / "diffs"
    diffs_path.mkdir(exist_ok=True)
    (diffs_path / f"{decision_id}.txt").write_text(diff)


def get_diff(decision_id: str) -> Optional[str]:
    path = Path.home() / ".decisions" / "diffs" / f"{decision_id}.txt"
    return path.read_text() if path.exists() else None
