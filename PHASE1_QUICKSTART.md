# keel — Quick Start: Implementation Phase 1

## What's Already Done ✅

1. **Updated `.github/copilot-instructions.md`** — Complete architecture guide
2. **Created `platform_utils.py`** — Cross-platform utilities (ready to use)
3. **Created `tool_injector.py`** — Tool-specific injection (ready to use)
4. **Updated `store.py`** — New Decision fields + schema migrations
5. **Documentation**: IMPLEMENTATION_ROADMAP.md, COMPLETION_SUMMARY.md, ARCHITECTURE.md

## Quick Start: Implement Phase 1.1 (Next 3-4 hours)

### Goal

Enhance `queue_writer.py` to capture prompt/output separately for all 7 source tools.

### Current State

```python
# queue_writer.py TODAY:
def main():
    parser.add_argument("--source", required=True)
    parser.add_argument("--type", default="prompt")
    parser.add_argument("--cwd", default="")
    parser.add_argument("--text", default="")
    # Reads from stdin or --text arg
    # Writes: {"id", "timestamp", "source", "type", "cwd", "text", "processed"}
```

### Changes Needed

```python
# queue_writer.py ENHANCED:
def main():
    parser.add_argument("--source", required=True,
        help="claude-code|copilot|gemini|cursor|antigravity|git|manual")
    parser.add_argument("--type", default="prompt")
    parser.add_argument("--cwd", default="")

    # NEW: separate prompt and output
    parser.add_argument("--prompt", default="", help="User prompt/input")
    parser.add_argument("--output", default="", help="LLM response/output")
    parser.add_argument("--text", default="", help="Combined text (fallback)")

    # Args parsing...

    # NEW: populate event with prompt + output
    event = {
        "id": _short_id(),
        "timestamp": datetime.utcnow().isoformat(),
        "source": args.source,
        "type": args.type,
        "cwd": args.cwd,
        "text": args.text,           # full text (optional)
        "prompt": args.prompt,       # isolated prompt (NEW)
        "output": args.output,       # isolated output (NEW)
        "processed": False,
    }

    # Append to queue.jsonl...
```

### Where It Gets Called From

**1. Claude Code** (existing)

```bash
python queue_writer.py --source claude-code --type prompt \
  --prompt "{user_prompt}" --output "{llm_response}" --cwd "$(pwd)"
```

**2. Copilot** (NEW — via shell wrapper)

```bash
# In ~/.zshrc:
copilot() {
    local prompt="$*"
    local output=$(api_call "$prompt")
    echo "$output" | python queue_writer.py \
        --source copilot --prompt "$prompt" --output "$output" --cwd "$(pwd)"
    echo "$output"  # Show to user
}
```

**3. Gemini CLI** (NEW — via shell wrapper)

```bash
# In ~/.zshrc:
gemini() {
    local prompt="$*"
    local output=$(/usr/local/bin/gemini "$@" 2>&1)
    echo "$output" | python queue_writer.py \
        --source gemini --prompt "$prompt" --output "$output" --cwd "$(pwd)"
    echo "$output"  # Show to user
}
```

**4. Cursor** (NEW — via editor hook, or wrapper)

```bash
python queue_writer.py --source cursor --type prompt \
  --prompt "{user_prompt}" --output "{llm_response}" --cwd "$(pwd)"
```

**5. Antigravity** (NEW — via shell wrapper)

```bash
# In ~/.zshrc:
antigravity() {
    local prompt="$*"
    local output=$(ag "$@" 2>&1)
    echo "$output" | python queue_writer.py \
        --source antigravity --prompt "$prompt" --output "$output" --cwd "$(pwd)"
    echo "$output"  # Show to user
}
```

**6. Git commit** (existing)

```bash
# In ~/.git-hooks/post-commit:
echo "$COMMIT_MSG" | python queue_writer.py \
    --source git --type commit --cwd "$(pwd)"
```

**7. Manual** (existing — CLI)

```bash
keel log --title "..." --choice "..." --reasoning "..."
# Internally calls queue_writer with --source manual
```

### Implementation Steps

#### Step 1: Update `queue_writer.py` (30 min)

```python
import argparse
from datetime import datetime
from pathlib import Path
import json
import sys

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

    # Build prompt/output from text if not provided separately
    prompt = args.prompt or args.text
    output = args.output

    # Read from stdin if prompt not provided
    if not prompt and not sys.stdin.isatty():
        stdin_data = sys.stdin.read().strip()
        # Try to parse as JSON (Claude Code sends JSON)
        try:
            data = json.loads(stdin_data)
            prompt = data.get("prompt", stdin_data)
            if not args.cwd:
                args.cwd = data.get("cwd", "")
        except (json.JSONDecodeError, TypeError):
            prompt = stdin_data

    if not prompt and not output:
        sys.exit(0)  # Nothing to log

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
        # Non-blocking: don't raise
        print(f"Warning: failed to log event: {e}", file=sys.stderr)

def _short_id():
    import uuid
    return str(uuid.uuid4())[:8]

if __name__ == "__main__":
    main()
```

#### Step 2: Test with all 7 sources (1 hour)

```bash
# Test 1: Claude Code mock
echo '{"prompt":"test prompt","output":"test output"}' | \
  python queue_writer.py --source claude-code --cwd /tmp

# Test 2: Copilot mock
python queue_writer.py --source copilot \
  --prompt "Write a function" --output "def foo(): pass" --cwd /tmp

# Test 3: Gemini mock
python queue_writer.py --source gemini \
  --prompt "Summarize this" --output "Summary..." --cwd /tmp

# Test 4: Cursor mock
python queue_writer.py --source cursor \
  --prompt "Fix this bug" --output "Bug fixed" --cwd /tmp

# Test 5: Antigravity mock
python queue_writer.py --source antigravity \
  --prompt "Generate code" --output "Code..." --cwd /tmp

# Test 6: Git mock
python queue_writer.py --source git --type commit \
  --text "feat: add new feature" --cwd /tmp

# Test 7: Manual mock (via keel log)
keel log --title "Decided X" --choice "Y" --reasoning "Because Z"

# Verify: Check queue.jsonl
cat ~/.keel/queue.jsonl | tail -10
```

#### Step 3: Verify event structure (30 min)

```bash
# Inspect last 3 events
tail -3 ~/.keel/queue.jsonl | python -m json.tool

# Should see:
# {
#   "id": "a1b2c3d4",
#   "timestamp": "2026-04-04T...",
#   "source": "copilot",
#   "type": "prompt",
#   "cwd": "/path/to/project",
#   "text": "",
#   "prompt": "Write a function",
#   "output": "def foo(): pass",
#   "processed": false
# }
```

### Phase 1.2: Update `processor.py` (Next 4-5 hours)

#### Goal

Extract isolated prompt/output from combined text when not already separated.

#### Implementation

```python
# In processor.py:

def _split_prompt_output(text: str, source: str) -> tuple[str, str]:
    """Split combined text into prompt and output based on source."""

    if source == "git":
        # Format: "COMMIT: {msg}\n\nCHANGED FILES:\n{diff}"
        if "COMMIT:" in text and "CHANGED FILES:" in text:
            commit_idx = text.find("COMMIT:")
            files_idx = text.find("CHANGED FILES:")
            commit_msg = text[commit_idx+8:files_idx].strip()
            changed = text[files_idx+14:].strip()
            return (commit_msg, changed)

    if source in ("gemini", "antigravity"):
        # Format: "User: {prompt}\n\nAssistant: {output}"
        if "User:" in text and "Assistant:" in text:
            user_idx = text.find("User:")
            asst_idx = text.find("Assistant:")
            prompt = text[user_idx+5:asst_idx].strip()
            output = text[asst_idx+10:].strip()
            return (prompt, output)

    # Fallback: return text as prompt, empty output
    return (text, "")

# In classify() function:
def classify(event: dict) -> dict:
    text = event.get("text", "")
    prompt = event.get("prompt", text)
    output = event.get("output", "")

    # Use prompt/output if available, otherwise try to split
    if not output and text:
        prompt, output = _split_prompt_output(text, event["source"])

    # Pass to LLM classifier
    classifier_text = f"Prompt: {prompt}\n\nOutput: {output}"
    ...
```

## Testing Checklist

- [ ] `queue_writer.py` accepts all 7 source types
- [ ] `--prompt` and `--output` args work separately
- [ ] Events are written to ~/.keel/queue.jsonl
- [ ] Event JSON structure has 9 fields (id, timestamp, source, type, cwd, text, prompt, output, processed)
- [ ] `keel process` reads the queue correctly
- [ ] No errors when processing mixed sources

## Files Modified So Far

| File                              | Status                |
| --------------------------------- | --------------------- |
| `.github/copilot-instructions.md` | ✅ Updated            |
| `platform_utils.py`               | ✅ Created            |
| `tool_injector.py`                | ✅ Created            |
| `store.py`                        | ✅ Updated            |
| `queue_writer.py`                 | ⏳ Ready to implement |
| `processor.py`                    | ⏳ Next to implement  |
| `install.py`                      | ⏳ Phase 1.3          |

## Commands to Try (After Implementation)

```bash
# After updating queue_writer.py:
python queue_writer.py --source copilot \
  --prompt "Write a hello world" \
  --output "print('Hello, World!')" \
  --cwd "$(pwd)"

# Check it was written:
tail -1 ~/.keel/queue.jsonl | python -m json.tool

# Run processor:
keel process

# Check decision was saved:
keel ls

# Show the decision with prompt/output:
keel show <decision_id>
```

## Next Phase (1.3): Update `install.py` for Cross-Platform Hooks

Once queue_writer.py is done, move to implementing cross-platform hook installation:

- macOS: Claude Code settings.json + LaunchAgent
- Linux: Shell wrappers + cron
- Windows: PowerShell wrappers + Task Scheduler

Reference: `IMPLEMENTATION_ROADMAP.md` Phase 1.3

---

**Status**: Ready to implement Phase 1.1 (queue_writer.py) ✅
