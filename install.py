"""Install hooks for Claude Code, Gemini CLI, and Git (cross-platform)."""

import json
import os
import stat
import subprocess
import platform as platform_module
from pathlib import Path

try:
    import platform_utils
except ImportError:
    platform_utils = None

# Absolute path to the queue_writer.py and cli.py scripts
SCRIPT_DIR = Path(__file__).parent.resolve()
QUEUE_WRITER = SCRIPT_DIR / "queue_writer.py"
CLI = SCRIPT_DIR / "cli.py"
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
    """Add shell function wrappers for Gemini CLI and other AI tools (cross-platform)."""
    # Detect OS and shell
    system = platform_module.system()
    
    if system == "Windows":
        # Windows: PowerShell support
        shell = platform_utils.get_shell()
        if shell == "pwsh" or shell == "powershell":
            _install_powershell_wrappers()
        else:
            print(f"  ⊘ Shell wrappers: unsupported shell {shell} on Windows")
        return
    
    # Unix-like systems (macOS, Linux)
    # ... rest of the existing code ...
    shell_env = os.environ.get("SHELL", "/bin/zsh")
    is_zsh = "zsh" in shell_env
    rc_file = Path.home() / (".zshrc" if is_zsh else ".bashrc")

    wrapper_script = Path.home() / ".keel" / "shell_wrappers.sh"
    wrapper_script.parent.mkdir(parents=True, exist_ok=True)

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
  local cmd="gemini $@"
  local output
  output=$(command gemini "$@")
  local exit_code=$?
  
  # Send to keel queue (using printf for real newlines)
  local payload
  payload=$(printf "User: %s\nAssistant:\n%s" "$cmd" "$output")
  echo "$payload" | {PYTHON} {QUEUE_WRITER} --source gemini --type prompt --cwd "$(pwd)" 2>/dev/null &
  
  echo "$output"
  return $exit_code
}}

# Cursor wrapper
cursor() {{
  _decide_log_prompt "cursor" "$@"
  command cursor "$@"
}}

# Antigravity wrapper
antigravity() {{
  _decide_log_prompt "antigravity" "$@"
  command antigravity "$@"
}}

# ChatGPT CLI wrapper (if used)
chatgpt() {{
  _decide_log_prompt "chatgpt" "$@"
  command chatgpt "$@"
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


def _install_powershell_wrappers():
    """Install PowerShell function wrappers for AI tools."""
    rc_file = platform_utils.get_rc_file()
    if not rc_file:
        return

    wrapper_script = Path.home() / ".keel" / "shell_wrappers.ps1"
    wrapper_script.parent.mkdir(parents=True, exist_ok=True)

    content = f"""
# ── keel: AI CLI wrappers (PowerShell) ─────────────────
function Invoke-DecideLogPrompt {{
    param($Source, $Args)
    # Find last non-flag arg
    $text = ""
    for ($i = 0; $i -lt $Args.Length; $i++) {{
        if ($Args[$i] -match "^-(p|prompt)$" -and ($i + 1) -lt $Args.Length) {{
            $text = $Args[$i+1]
            break
        }}
        if ($Args[$i] -notmatch "^-") {{ $text = $Args[$i] }}
    }}
    if ($text) {{
        $text | & "{PYTHON}" "{QUEUE_WRITER}" --source $Source --type prompt --cwd (Get-Location)
    }}
}}

function gemini {{
    $output = command gemini @args
    $status = $LASTEXITCODE
    
    $payload = "User: $($args -join ' ')\nAssistant:\n$output"
    $payload | & "{PYTHON}" "{QUEUE_WRITER}" --source gemini --type prompt --cwd (Get-Location)
    
    $output
    return $status
}}

function cursor {{
    Invoke-DecideLogPrompt -Source "cursor" -Args $args
    command cursor @args
}}

function antigravity {{
    Invoke-DecideLogPrompt -Source "antigravity" -Args $args
    command antigravity @args
}}
# ────────────────────────────────────────────────────────
"""
    wrapper_script.write_text(content)

    # Add dot-source line to profile
    source_line = f'\n. "{wrapper_script}"'
    rc_content = rc_file.read_text() if rc_file.exists() else ""

    if str(wrapper_script) not in rc_content:
        rc_file.parent.mkdir(parents=True, exist_ok=True)
        with open(rc_file, "a") as f:
            f.write(source_line)
        print(f"  ✓ PowerShell wrappers installed → {wrapper_script}")
        print(f"    Added dot-source to {rc_file}")
    else:
        print(f"  PowerShell wrappers: already in {rc_file}")


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


def install_background_processor():
    """Install background processor using OS-specific scheduler via platform_utils.
    
    - macOS: LaunchAgent
    - Linux: cron
    - Windows: Task Scheduler
    """
    if not platform_utils:
        print("  ⊘ platform_utils not found, skipping background install")
        return

    # 1. Collector (Process queue every 15 min)
    collector_cmd = f"{PYTHON} {CLI} process --quiet"
    ok = platform_utils.install_cron_job(
        label="collector",
        command=collector_cmd,
        interval_minutes=15
    )
    if ok:
        print("  ✓ Background collector installed (every 15 min)")
    else:
        print("  ✗ Failed to install collector")

    # 2. Sync (Sync all projects every 6 hours)
    sync_cmd = f"{PYTHON} {CLI} sync --all --quiet"
    ok = platform_utils.install_cron_job(
        label="sync",
        command=sync_cmd,
        interval_minutes=360 # 6 hours
    )
    if ok:
        print("  ✓ Background sync installed (every 6 hours)")

    # 3. Profile (Refresh persona daily)
    # Note: simple interval for now as calendar support is limited in platform_utils
    profile_cmd = f"{PYTHON} {CLI} profile --build --inject-all --quiet"
    ok = platform_utils.install_cron_job(
        label="profile",
        command=profile_cmd,
        interval_minutes=1440 # 24 hours
    )
    if ok:
        print("  ✓ Background profile refresh installed (daily)")


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
