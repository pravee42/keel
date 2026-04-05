#!/usr/bin/env python3
"""Lightweight hook script — writes raw events to queue. Must be fast (called on every prompt)."""

import json
import sys
import argparse
from datetime import datetime
from pathlib import Path

try:
    import platform_utils
    QUEUE_PATH = platform_utils.get_keel_home() / "queue.jsonl"
except ImportError:
    QUEUE_PATH = Path.home() / ".keel" / "queue.jsonl"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True,
                        help="claude-code|copilot|gemini|cursor|antigravity|git|manual")
    parser.add_argument("--type", default="prompt",
                        help="prompt|commit|message")
    parser.add_argument("--cwd", default="")
    parser.add_argument("--prompt", default="",
                        help="User prompt/input")
    parser.add_argument("--output", default="",
                        help="LLM response/output")
    parser.add_argument("--text", default="",
                        help="Combined text (fallback if --prompt not provided)")
    args = parser.parse_args()

    # Build prompt/output from args
    prompt = args.prompt or args.text
    output = args.output

    # Read from stdin if prompt not provided
    if not prompt and not sys.stdin.isatty():
        stdin_data = sys.stdin.read().strip()
        # Try to parse as JSON (Claude Code sends JSON)
        try:
            data = json.loads(stdin_data)
            prompt = data.get("prompt", stdin_data)
            output = output or data.get("output", "")
            if not args.cwd:
                args.cwd = data.get("cwd", "")
        except (json.JSONDecodeError, TypeError):
            prompt = stdin_data

    if not prompt and not output:
        sys.exit(0)

    event = {
        "id": _short_id(),
        "timestamp": datetime.utcnow().isoformat(),
        "source": args.source,
        "type": args.type,
        "cwd": args.cwd,
        "text": args.text,
        "prompt": prompt,
        "output": output,
        "processed": False,
    }

    try:
        QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(QUEUE_PATH, "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception as e:
        print(f"Warning: failed to log event: {e}", file=sys.stderr)


def _short_id():
    import uuid
    return str(uuid.uuid4())[:8]


if __name__ == "__main__":
    main()
