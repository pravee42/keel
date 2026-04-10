"""Process queue events: classify → extract decision → consistency check → notify."""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

try:
    import platform_utils
    QUEUE_PATH = platform_utils.get_keel_home() / "queue.jsonl"
    PROCESSED_PATH = platform_utils.get_keel_home() / "processed.jsonl"
except ImportError:
    QUEUE_PATH = Path.home() / ".keel" / "queue.jsonl"
    PROCESSED_PATH = Path.home() / ".keel" / "processed.jsonl"

import llm
import store
import analyzer

try:
    import projects
except ImportError:
    projects = None


# ─────────────────────────────────────────────
# Unified Triage & Extraction
# ─────────────────────────────────────────────

TRIAGE_EXTRACTION_PROMPT = """Analyze this {source} {type} to find Requirements and Decisions.

**Requirements:** Constraints, goals, or functional needs (e.g., "Must be fast", "Use PostgreSQL").
**Decisions:** Implementation choices made to fulfill requirements (e.g., "Using an index for speed").

Content:
{text}

Reply with ONLY valid JSON:
{{
  "is_requirement": true/false,
  "requirement_text": "what must be achieved",
  "requirement_type": "Functional|Technical|Constraint|Business",
  "requirement_priority": "High|Medium|Low",
  
  "is_decision": true/false,
  "decision_title": "short title",
  "decision_domain": "code|writing|business|life|other",
  "decision_context": "situation",
  "decision_options": "alternatives considered",
  "decision_choice": "what was decided",
  "decision_reasoning": "why",
  "decision_alternatives": ["inferred", "common", "alternatives"],
  "is_implicit": true/false (true if inferred from code/diff but not explicitly stated)
}}"""


def _split_prompt_output(text: str, source: str) -> Tuple[str, str]:
    """Split combined text into prompt and output based on source heuristics."""
    if source == "git":
        if "COMMIT:" in text and "CHANGED FILES:" in text:
            commit_idx = text.find("COMMIT:") + len("COMMIT:")
            files_idx = text.find("CHANGED FILES:")
            commit_msg = text[commit_idx:files_idx].strip()
            changed = text[files_idx + len("CHANGED FILES:"):].strip()
            return (commit_msg, changed)
    
    if source in ("gemini", "antigravity"):
        if "User:" in text and "Assistant:" in text:
            user_idx = text.find("User:") + len("User:")
            asst_idx = text.find("Assistant:")
            prompt = text[user_idx:asst_idx].strip()
            output = text[asst_idx + len("Assistant:"):].strip()
            return (prompt, output)
    
    return (text, "")


def _parse_json(text: str, fallback: dict) -> dict:
    """Extract the first valid JSON object from text, ignoring trailing content."""
    text = text.strip()
    # Try direct parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Find the first '{' and decode only the first complete object
    start = text.find("{")
    if start == -1:
        return fallback
    try:
        obj, _ = json.JSONDecoder().raw_decode(text, start)
        return obj
    except json.JSONDecodeError:
        return fallback


def triage_and_extract(event: dict) -> dict:
    """Single-pass triage and extraction for efficiency."""
    text = llm.complete([{"role": "user", "content": TRIAGE_EXTRACTION_PROMPT.format(
        source=event["source"],
        type=event["type"],
        text=event["text"][:3000],
    )}], max_tokens=1536).strip()
    return _parse_json(text, {})


# ─────────────────────────────────────────────
# Step 3: Notify user
# ─────────────────────────────────────────────

def notify(title: str, message: str):
    """macOS notification. Silently fails on other platforms."""
    try:
        script = f'display notification "{message[:200]}" with title "keel: {title}"'
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
    """Process unprocessed events from queue. Called by `keel process` or cron."""
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


def _detect_project(cwd: str) -> str:
    """Return the git root for cwd, or '' if not inside a git repo."""
    if not cwd:
        return ""
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return ""


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
    """Triage, extract, store, and check one event."""
    if event.get("type") == "test":
        if verbose:
            print(f"  [{event['source']}] (test event) → skipped")
        return {"skipped": True, "reason": "test event"}

    if verbose:
        source = event["source"]
        preview = event["text"][:60].replace("\n", " ")
        print(f"  [{source}] {preview}...")

    # Step 1: Triage and Extract
    extracted = triage_and_extract(event)
    is_req = extracted.get("is_requirement", False)
    is_dec = extracted.get("is_decision", False)

    if not is_req and not is_dec:
        if verbose:
            print("    → skipped (no requirement or decision found)")
        return {"skipped": True, "reason": "nothing to track"}

    # Step 2: Handle Requirement
    req_id = None
    if is_req:
        req_id = store.new_id()
        r = store.Requirement(
            id=req_id,
            timestamp=event["timestamp"],
            text=extracted.get("requirement_text", ""),
            type=extracted.get("requirement_type", "Functional"),
            priority=extracted.get("requirement_priority", "Medium"),
            project=_detect_project(event.get("cwd", "")),
            source_event_id=event["id"]
        )
        store.save_requirement(r)
        if verbose:
            print(f"    → saved requirement [{req_id}]: {r.text[:50]}...")

    # Step 3: Handle Decision
    dec_id = None
    if is_dec:
        dec_id = store.new_id()
        # Extract prompt/output if needed for Decision
        prompt = event.get("prompt", "")
        output = event.get("output", "")
        if not prompt and not output and event.get("text"):
            prompt, output = _split_prompt_output(event["text"], event["source"])

        d = store.Decision(
            id=dec_id,
            timestamp=event["timestamp"],
            domain=extracted.get("decision_domain", "other"),
            title=extracted.get("decision_title", "Untitled"),
            context=extracted.get("decision_context", ""),
            options=extracted.get("decision_options", ""),
            choice=extracted.get("decision_choice", ""),
            reasoning=extracted.get("decision_reasoning", ""),
            principles="[]",
            outcome="",
            tags=json.dumps(_detect_tags(event["text"], extracted)),
            paths=json.dumps(_detect_paths(event)),
            project=_detect_project(event.get("cwd", "")),
            source_tool=event.get("source", "manual"),
            prompt=prompt,
            output=output,
            is_implicit=1 if extracted.get("is_implicit") else 0,
            alternatives=json.dumps(extracted.get("decision_alternatives", []))
        )

        # Extract principles
        try:
            principles = analyzer.extract_principles(d)
            d.principles = json.dumps(principles)
        except Exception:
            pass

        store.save(d)
        
        if verbose:
            implicit_str = " (IMPLICIT)" if d.is_implicit else ""
            print(f"    → saved decision [{dec_id}]{implicit_str}: {d.title}")

        # Trigger per-project CLAUDE.md sync (non-blocking)
        if d.project:
            try:
                import projects as proj_mod
                proj_mod.sync_if_stale(d.project, quiet=True)
            except Exception:
                pass

        # Step 4: Consistency check
        history = [h for h in store.get_all() if h.id != d.id]
        if history:
            try:
                similar = analyzer.find_similar(d, history, top_n=2)
                if similar:
                    diff = analyzer.consistency_diff(d, similar)
                    flagged = any(w in diff.lower() for w in
                                  ["inconsist", "contradict", "conflict", "changed", "different from"])
                    if flagged:
                        notify_inconsistency(d.title, diff)
                        _save_diff(d.id, diff)
            except Exception:
                pass

    # Step 5: Link if both exist
    if req_id and dec_id:
        store.link_requirement_decision(req_id, dec_id)

    return {"saved": True, "req_id": req_id, "dec_id": dec_id}


def _save_diff(decision_id: str, diff: str):
    """Save consistency diff to sidecar file."""
    diffs_path = Path.home() / ".keel" / "diffs"
    diffs_path.mkdir(exist_ok=True)
    (diffs_path / f"{decision_id}.txt").write_text(diff)


def get_diff(decision_id: str) -> Optional[str]:
    path = Path.home() / ".keel" / "diffs" / f"{decision_id}.txt"
    return path.read_text() if path.exists() else None
