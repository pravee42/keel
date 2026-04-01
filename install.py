"""Install hooks for Claude Code, Gemini CLI, and Git."""

import json
import os
import stat
import subprocess
from pathlib import Path

# Absolute path to the queue_writer.py script
SCRIPT_DIR = Path(__file__).parent.resolve()
QUEUE_WRITER = SCRIPT_DIR / "queue_writer.py"
PYTHON = os.sys.executable


def install_claude_code():
    """Add UserPromptSubmit hook to ~/.claude/settings.json"""
    settings_path = Path.home() / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    settings = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text())
        except json.JSONDecodeError:
            pass

    hook_command = f'{PYTHON} {QUEUE_WRITER} --source claude-code --type prompt'
    hook_entry = {"type": "command", "command": hook_command}

    hooks = settings.setdefault("hooks", {})
    prompt_hooks = hooks.setdefault("UserPromptSubmit", [])

    # Check if already installed
    for h in prompt_hooks:
        if isinstance(h, dict) and h.get("hooks"):
            for inner in h["hooks"]:
                if QUEUE_WRITER.name in inner.get("command", ""):
                    print("  Claude Code hook: already installed")
                    return

    prompt_hooks.append({"matcher": "", "hooks": [hook_entry]})
    settings_path.write_text(json.dumps(settings, indent=2))
    print("  ✓ Claude Code hook installed (~/.claude/settings.json)")


def install_git_hook():
    """Install a global git post-commit hook."""
    # Set up global hooks directory
    hooks_dir = Path.home() / ".git-hooks"
    hooks_dir.mkdir(exist_ok=True)

    hook_script = hooks_dir / "post-commit"
    hook_content = f"""#!/bin/sh
# keel — log git commits for decision tracking
COMMIT_MSG=$(git log -1 --pretty=%B)
DIFF_STAT=$(git diff HEAD~1 HEAD --stat 2>/dev/null || git show --stat HEAD)
FULL_TEXT="COMMIT: $COMMIT_MSG

CHANGED FILES:
$DIFF_STAT"
echo "$FULL_TEXT" | {PYTHON} {QUEUE_WRITER} --source git --type commit --cwd "$(pwd)"
"""
    hook_script.write_text(hook_content)
    hook_script.chmod(hook_script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)

    # Configure git to use global hooks dir
    result = subprocess.run(
        ["git", "config", "--global", "core.hooksPath", str(hooks_dir)],
        capture_output=True
    )
    if result.returncode == 0:
        print(f"  ✓ Git post-commit hook installed ({hooks_dir})")
    else:
        print(f"  ✗ Git config failed: {result.stderr.decode()}")
        print(f"    Manual fix: git config --global core.hooksPath {hooks_dir}")


def install_shell_wrappers():
    """Add shell function wrappers for Gemini CLI and other AI tools."""
    wrapper_script = Path.home() / ".keel" / "shell_wrappers.sh"
    wrapper_script.parent.mkdir(exist_ok=True)

    # Detect shell
    shell = os.environ.get("SHELL", "/bin/zsh")
    rc_file = Path.home() / (".zshrc" if "zsh" in shell else ".bashrc")

    content = f"""
# ── keel: AI CLI wrappers ──────────────────────────────
_decide_log_prompt() {{
  local source="$1"
  shift
  # Try to extract -p / --prompt flag or last positional arg
  local text=""
  local capture_next=0
  for arg in "$@"; do
    if [ $capture_next -eq 1 ]; then
      text="$arg"
      break
    fi
    case "$arg" in
      -p|--prompt) capture_next=1 ;;
      -*) ;;          # skip other flags
      *) text="$arg" ;;  # last positional
    esac
  done
  if [ -n "$text" ]; then
    echo "$text" | {PYTHON} {QUEUE_WRITER} --source "$source" --type prompt --cwd "$(pwd)" 2>/dev/null &
  fi
}}

# Gemini CLI wrapper
gemini() {{
  _decide_log_prompt "gemini" "$@"
  command gemini "$@"
}}

# ChatGPT CLI wrapper (if you use it)
chatgpt() {{
  _decide_log_prompt "chatgpt" "$@"
  command chatgpt "$@"
}}

# Cursor (if used from CLI)
cursor() {{
  _decide_log_prompt "cursor" "$@"
  command cursor "$@"
}}

# Aider wrapper
aider() {{
  _decide_log_prompt "aider" "$@"
  command aider "$@"
}}
# ─────────────────────────────────────────────────────────
"""
    wrapper_script.write_text(content)

    # Add source line to rc file if not already there
    source_line = f'\n[ -f "{wrapper_script}" ] && source "{wrapper_script}"'
    rc_content = rc_file.read_text() if rc_file.exists() else ""

    if str(wrapper_script) not in rc_content:
        with open(rc_file, "a") as f:
            f.write(source_line)
        print(f"  ✓ Shell wrappers installed → {wrapper_script}")
        print(f"    Added source line to {rc_file}")
        print(f"    Run: source {rc_file}")
    else:
        print(f"  Shell wrappers: already in {rc_file}")


def install_launch_agents():
    """Install macOS LaunchAgents for background processing and daily persona refresh."""
    import service
    service.install_agents(verbose=True)


def install_cron():
    """Add cron jobs: process queue every 15 min + weekly digest on Sundays."""
    process_cmd = f"*/15 * * * * {PYTHON} {SCRIPT_DIR / 'cli.py'} process --quiet 2>/dev/null"
    # Sunday 9am
    digest_cmd  = f"0 9 * * 0 {PYTHON} {SCRIPT_DIR / 'cli.py'} weekly --no-save 2>/dev/null | mail -s 'keel: weekly digest' $USER 2>/dev/null || true"

    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    current = result.stdout if result.returncode == 0 else ""

    to_add = []
    if "keel" not in current or "process" not in current:
        to_add.append(process_cmd)
    if "weekly" not in current:
        to_add.append(digest_cmd)

    if not to_add:
        print("  Cron: already installed")
        return

    new_crontab = current.rstrip() + "\n" + "\n".join(to_add) + "\n"
    p = subprocess.run(["crontab", "-"], input=new_crontab, text=True, capture_output=True)
    if p.returncode == 0:
        print("  ✓ Cron jobs installed:")
        print("      · every 15 min — process queue")
        print("      · Sunday 9am  — weekly digest")
    else:
        print(f"  ✗ Cron install failed")
        print(f"    Manual: add to crontab:")
        for cmd in to_add:
            print(f"      {cmd}")


def uninstall_claude_code():
    settings_path = Path.home() / ".claude" / "settings.json"
    if not settings_path.exists():
        return
    settings = json.loads(settings_path.read_text())
    hooks = settings.get("hooks", {})
    prompt_hooks = hooks.get("UserPromptSubmit", [])
    filtered = [h for h in prompt_hooks
                if not any(QUEUE_WRITER.name in inner.get("command", "")
                           for inner in h.get("hooks", []))]
    settings["hooks"]["UserPromptSubmit"] = filtered
    settings_path.write_text(json.dumps(settings, indent=2))
    print("  ✓ Claude Code hook removed")


def uninstall_git_hook():
    subprocess.run(["git", "config", "--global", "--unset", "core.hooksPath"],
                   capture_output=True)
    print("  ✓ Git global hooksPath unset")
