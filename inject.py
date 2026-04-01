"""Inject the developer persona into Claude Code, Gemini, and other tools."""

import json
import re
import subprocess
from pathlib import Path
from typing import Optional

PERSONA_PATH = Path.home() / ".decisions" / "persona.md"

# ─────────────────────────────────────────────
# Injection targets
# ─────────────────────────────────────────────

TARGETS = {
    "claude-code-global": {
        "label": "Claude Code (global)",
        "path":  Path.home() / ".claude" / "CLAUDE.md",
        "description": "Loaded automatically in every Claude Code session",
    },
    "gemini": {
        "label": "Gemini CLI",
        "path":  Path.home() / ".gemini" / "system_prompt.md",
        "description": "Pass via: gemini --system-prompt ~/.gemini/system_prompt.md",
    },
    "openai": {
        "label": "OpenAI / ChatGPT CLI",
        "path":  Path.home() / ".openai" / "system_prompt.md",
        "description": "Pass via: chatgpt --system ~/.openai/system_prompt.md",
    },
}

MARKER_START = "<!-- decide:persona:start -->"
MARKER_END   = "<!-- decide:persona:end -->"


def _wrap(content: str) -> str:
    return f"{MARKER_START}\n{content}\n{MARKER_END}"


def _upsert(file_path: Path, content: str) -> None:
    """Insert or replace the persona block in a file."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    existing = file_path.read_text() if file_path.exists() else ""
    block = _wrap(content)

    if MARKER_START in existing:
        updated = re.sub(
            rf"{re.escape(MARKER_START)}.*?{re.escape(MARKER_END)}",
            block,
            existing,
            flags=re.DOTALL,
        )
    else:
        updated = existing.rstrip() + ("\n\n" if existing else "") + block + "\n"

    file_path.write_text(updated)


def inject(targets: Optional[list] = None, persona_content: Optional[str] = None) -> dict:
    """Inject persona into specified targets. Returns {target: path} for successes."""
    content = persona_content or (PERSONA_PATH.read_text() if PERSONA_PATH.exists() else None)
    if not content:
        raise RuntimeError("No persona found. Run: decide profile --build")

    selected = {k: v for k, v in TARGETS.items()
                if targets is None or k in targets}

    results = {}
    for key, info in selected.items():
        try:
            _upsert(info["path"], content)
            results[key] = info["path"]
        except Exception as e:
            results[key] = f"ERROR: {e}"

    return results


def remove(targets: Optional[list] = None) -> None:
    """Remove persona block from injection targets."""
    selected = {k: v for k, v in TARGETS.items()
                if targets is None or k in targets}

    for key, info in selected.items():
        path = info["path"]
        if not path.exists():
            continue
        content = path.read_text()
        if MARKER_START not in content:
            continue
        cleaned = re.sub(
            rf"\n*{re.escape(MARKER_START)}.*?{re.escape(MARKER_END)}\n*",
            "\n",
            content,
            flags=re.DOTALL,
        )
        path.write_text(cleaned)


def injection_status() -> dict:
    """Check which targets currently have the persona injected."""
    status = {}
    for key, info in TARGETS.items():
        path = info["path"]
        if not path.exists():
            status[key] = "not injected"
        elif MARKER_START in path.read_text():
            status[key] = "injected"
        else:
            status[key] = "file exists, not injected"
    return status
