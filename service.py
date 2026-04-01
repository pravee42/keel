"""macOS LaunchAgent setup — replaces cron for reliable background operation."""

import os
import plistlib
import subprocess
from pathlib import Path

SCRIPT_DIR    = Path(__file__).parent.resolve()
PYTHON        = SCRIPT_DIR / ".venv" / "bin" / "python"
CLI           = SCRIPT_DIR / "cli.py"
LAUNCH_AGENTS = Path.home() / "Library" / "LaunchAgents"

AGENTS = {
    # Process queue every 15 min
    "com.keel.collector": {
        "label":       "com.keel.collector",
        "description": "keel — background queue processor (every 15 min)",
        "args":        [str(PYTHON), str(CLI), "process", "--quiet"],
        "interval":    900,    # seconds
        "run_at_load": True,
    },
    # Refresh persona daily at 7am + inject into all tools
    "com.keel.profile": {
        "label":       "com.keel.profile",
        "description": "keel — daily persona refresh + injection",
        "args":        [str(PYTHON), str(CLI), "profile", "--build", "--inject-all", "--quiet"],
        "calendar": {"Hour": 7, "Minute": 0},  # daily at 7am
        "run_at_load": False,
    },
    # Sync per-project context every 6 hours (backstop for cross-project arch changes)
    "com.keel.sync": {
        "label":       "com.keel.sync",
        "description": "keel — per-project CLAUDE.md context sync (every 6 hours)",
        "args":        [str(PYTHON), str(CLI), "sync", "--all", "--quiet"],
        "interval":    21600,  # 6 hours
        "run_at_load": True,
    },
}


def _plist_path(label: str) -> Path:
    return LAUNCH_AGENTS / f"{label}.plist"


def _build_plist(agent: dict) -> dict:
    plist: dict = {
        "Label":                 agent["label"],
        "ProgramArguments":      agent["args"],
        "StandardOutPath":       str(Path.home() / ".keel" / f"{agent['label']}.log"),
        "StandardErrorPath":     str(Path.home() / ".keel" / f"{agent['label']}.err"),
        "RunAtLoad":             agent.get("run_at_load", False),
    }
    if "interval" in agent:
        plist["StartInterval"] = agent["interval"]
    if "calendar" in agent:
        plist["StartCalendarInterval"] = agent["calendar"]
    return plist


def install_agents(verbose: bool = True) -> None:
    LAUNCH_AGENTS.mkdir(parents=True, exist_ok=True)
    Path.home().joinpath(".keel").mkdir(exist_ok=True)

    for label, agent in AGENTS.items():
        path = _plist_path(label)
        plist_data = _build_plist(agent)

        with open(path, "wb") as f:
            plistlib.dump(plist_data, f)

        # Unload first if already running, then load
        subprocess.run(["launchctl", "unload", str(path)],
                       capture_output=True)
        result = subprocess.run(["launchctl", "load", str(path)],
                                capture_output=True, text=True)

        if verbose:
            if result.returncode == 0:
                schedule = (f"every {agent['interval']//60} min"
                            if "interval" in agent
                            else f"daily at {agent.get('calendar', {}).get('Hour', '?')}am")
                print(f"  ✓ {label}  [{schedule}]")
            else:
                print(f"  ✗ {label}: {result.stderr.strip()}")


def uninstall_agents(verbose: bool = True) -> None:
    for label in AGENTS:
        path = _plist_path(label)
        if path.exists():
            subprocess.run(["launchctl", "unload", str(path)], capture_output=True)
            path.unlink()
            if verbose:
                print(f"  ✓ removed {label}")


def agent_status() -> dict:
    status = {}
    for label in AGENTS:
        path = _plist_path(label)
        if not path.exists():
            status[label] = "not installed"
            continue
        result = subprocess.run(
            ["launchctl", "list", label],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            # Parse PID from launchctl list output
            lines = result.stdout.strip().split("\n")
            pid_line = next((l for l in lines if "PID" in l or lines[0]), lines[0] if lines else "")
            status[label] = "running" if result.stdout.strip() else "loaded"
        else:
            status[label] = "stopped"
    return status


def trigger_now(label: str) -> bool:
    """Manually trigger a LaunchAgent job right now."""
    result = subprocess.run(
        ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}/{label}"],
        capture_output=True, text=True,
    )
    return result.returncode == 0
