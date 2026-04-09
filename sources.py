"""Manage event sources (claude-code, copilot, gemini, cursor, etc.) and their status."""

import os
import json
import subprocess
import platform
from pathlib import Path
from typing import Dict, List, Optional

import config
import platform_utils

# Metadata for all supported event sources
SUPPORTED_SOURCES = {
    "claude-code": {
        "label": "Claude Code",
        "type": "Editor Extension",
        "description": "UserPromptSubmit hook in ~/.claude/settings.json",
        "install_method": "hook",
    },
    "copilot": {
        "label": "GitHub Copilot",
        "type": "IDE Extension",
        "description": "LSP/telemetry capture or shell wrapper",
        "install_method": "hook",
    },
    "gemini": {
        "label": "Gemini CLI",
        "type": "CLI Wrapper",
        "description": "Shell function wrapper for 'gemini' command",
        "install_method": "wrapper",
    },
    "cursor": {
        "label": "Cursor Editor",
        "type": "Editor wrapper",
        "description": "Shell function wrapper for 'cursor' command",
        "install_method": "wrapper",
    },
    "antigravity": {
        "label": "Antigravity CLI",
        "type": "CLI Wrapper",
        "description": "Shell function wrapper for 'antigravity' command",
        "install_method": "wrapper",
    },
    "git": {
        "label": "Git Commit",
        "type": "Git Hook",
        "description": "Global post-commit hook in ~/.git-hooks/",
        "install_method": "hook",
    },
    "manual": {
        "label": "Manual Log",
        "type": "CLI Command",
        "description": "Direct logging via 'keel log'",
        "install_method": "builtin",
    },
}

def get_status() -> Dict[str, dict]:
    """Check the installation and enabled status of all sources."""
    cfg = config.load()
    disabled = cfg.get("disabled_sources", [])
    
    status = {}
    for key, info in SUPPORTED_SOURCES.items():
        is_disabled = key in disabled
        is_installed = _check_installed(key)
        
        status[key] = {
            **info,
            "installed": is_installed,
            "enabled": not is_disabled,
        }
    return status

def _check_installed(source: str) -> bool:
    """Heuristic check for source installation."""
    if source == "claude-code":
        p = Path.home() / ".claude" / "settings.json"
        return p.exists() and "queue_writer" in p.read_text()
    
    if source == "git":
        # Check if git core.hooksPath is set
        try:
            res = subprocess.run(["git", "config", "--global", "core.hooksPath"], 
                               capture_output=True, text=True)
            return "keel" in res.stdout or ".git-hooks" in res.stdout
        except:
            return False
            
    if source in ("gemini", "cursor", "antigravity"):
        # Check if wrapper is in rc file (bash/zsh)
        files_to_check = []
        rc = platform_utils.get_rc_file()
        if rc: files_to_check.append(rc)
        
        # Also check the dedicated keel wrapper script
        keel_sh = Path.home() / ".keel" / "shell_wrappers.sh"
        if keel_sh.exists(): files_to_check.append(keel_sh)
        
        for p in files_to_check:
            if p.exists():
                content = p.read_text()
                if f"{source}()" in content or f"{source} ()" in content or f"function {source}" in content:
                    return True
        
        # Check for powershell wrapper script
        ps_wrapper = Path.home() / ".keel" / "shell_wrappers.ps1"
        if ps_wrapper.exists():
            if f"function {source}" in ps_wrapper.read_text():
                return True
        return False
        
    if source == "copilot":
        # Check if .copilot-instructions.md exists in current dir (as a proxy)
        return Path(".copilot-instructions.md").exists()
    
    if source == "manual":
        return True
        
    return False

def set_enabled(source: str, enabled: bool):
    """Enable or disable a source in the config."""
    if source not in SUPPORTED_SOURCES:
        raise ValueError(f"Unknown source: {source}")
        
    cfg = config.load()
    disabled = set(cfg.get("disabled_sources", []))
    
    if enabled:
        disabled.discard(source)
    else:
        disabled.add(source)
        
    cfg["disabled_sources"] = list(disabled)
    config.save(cfg)

def test_source(source: str) -> bool:
    """Test if a source can successfully write to the queue."""
    if source not in SUPPORTED_SOURCES:
        return False
        
    # We test by running queue_writer.py directly for that source
    # with a "test" payload.
    script_dir = Path(__file__).parent.resolve()
    qw = script_dir / "queue_writer.py"
    
    try:
        subprocess.run([
            os.sys.executable, str(qw),
            "--source", source,
            "--type", "test",
            "--text", "keel-source-test-ping",
            "--cwd", os.getcwd()
        ], check=True, capture_output=True)
        return True
    except:
        return False

def install_source(source: str) -> bool:
    """Trigger installation for a specific source."""
    import install
    if source == "claude-code":
        install.install_claude_code()
        return True
    if source == "git":
        install.install_git_hook()
        return True
    if source in ("gemini", "cursor", "antigravity"):
        install.install_shell_wrappers()
        return True
    return False
