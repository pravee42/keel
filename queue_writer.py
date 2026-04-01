#!/usr/bin/env python3
"""Lightweight hook script — writes raw events to queue. Must be fast (called on every prompt)."""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

QUEUE_PATH = Path.home() / ".decisions" / "queue.jsonl"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True,
                        help="claude-code | gemini | git | chatgpt | cursor | manual")
    parser.add_argument("--type", default="prompt",
                        help="prompt | commit | message")
    parser.add_argument("--cwd", default="")
    parser.add_argument("--text", default="",
                        help="Text content (or read from stdin if not provided)")
    args = parser.parse_args()

    # Read text from stdin (hook piped input) or --text arg
    if args.text:
        text = args.text
    elif not sys.stdin.isatty():
        raw = sys.stdin.read().strip()
        # Claude Code sends JSON on stdin for UserPromptSubmit
        try:
            data = json.loads(raw)
            text = data.get("prompt", raw)
            if not args.cwd:
                args.cwd = data.get("cwd", "")
        except (json.JSONDecodeError, TypeError):
            text = raw
    else:
        text = ""

    if not text:
        sys.exit(0)

    event = {
        "id": _short_id(),
        "timestamp": datetime.utcnow().isoformat(),
        "source": args.source,
        "type": args.type,
        "cwd": args.cwd,
        "text": text,
        "processed": False,
    }

    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(QUEUE_PATH, "a") as f:
        f.write(json.dumps(event) + "\n")


def _short_id():
    import uuid
    return str(uuid.uuid4())[:8]


if __name__ == "__main__":
    main()
