"""Cross-platform utilities: path resolution, process management, shell detection."""

import os
import platform
import subprocess
from pathlib import Path
from typing import Optional


def get_os() -> str:
    """Return normalized OS name: 'Darwin', 'Linux', or 'Windows'."""
    return platform.system()


def get_keel_home() -> Path:
    """Return ~/.keel/ with cross-platform support.
    
    Returns:
        Path object for:
        - Linux/macOS: ~/.keel/
        - Windows: APPDATA/keel/ (typically C:\\Users\\username\\AppData\\Roaming\\keel\\)
    """
    if get_os() == "Windows":
        # Use APPDATA for roaming profile (preferred for sync)
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "keel"
        # Fallback to home directory
        return Path.home() / "AppData" / "Roaming" / "keel"
    else:
        # macOS and Linux use ~/.keel/
        return Path.home() / ".keel"


def get_shell() -> str:
    """Detect user's shell.
    
    Returns:
        Shell name: 'zsh', 'bash', 'pwsh' (PowerShell), 'cmd', or 'unknown'
    """
    shell_env = os.environ.get("SHELL", "")
    
    # Unix-like: check SHELL env var
    if shell_env:
        shell_name = Path(shell_env).name
        if shell_name in ("zsh", "bash", "sh", "ksh", "fish"):
            return shell_name
    
    # Windows: check for PowerShell or cmd
    if get_os() == "Windows":
        # Check if pwsh (PowerShell Core) is available
        if subprocess.run(["where", "pwsh"], capture_output=True).returncode == 0:
            return "pwsh"
        # Fallback to cmd
        return "cmd"
    
    # Fallback
    return "bash"


def get_rc_file() -> Path:
    """Return the appropriate shell rc file for the current shell.
    
    Returns:
        Path to:
        - ~/.zshrc (for zsh)
        - ~/.bashrc (for bash)
        - ~/.config/PowerShell/profile.ps1 (for PowerShell)
        - Falls back to ~/.bashrc if uncertain
    """
    shell = get_shell()
    
    if shell == "zsh":
        return Path.home() / ".zshrc"
    elif shell == "pwsh":
        # PowerShell profile (Core and Windows PowerShell)
        if get_os() == "Windows":
            return Path.home() / "Documents" / "PowerShell" / "profile.ps1"
        else:
            return Path.home() / ".config" / "PowerShell" / "profile.ps1"
    elif shell == "cmd":
        # cmd doesn't have a persistent rc file; would need to modify registry or use AutoRun
        return None
    else:
        # Default to bash
        return Path.home() / ".bashrc"


def install_cron_job(
    label: str,
    command: str,
    interval_minutes: int = 15,
    start_time: str = "07:00"  # HH:MM format
) -> bool:
    """Install a recurring background job (OS-specific).
    
    Args:
        label: Descriptive name for the job (e.g., "keel-processor")
        command: Full command to run (e.g., "python3 /path/to/processor.py")
        interval_minutes: How often to run (15, 60, etc.)
        start_time: For daily jobs, time to start (HH:MM format)
    
    Returns:
        True if successful, False otherwise
    """
    os_name = get_os()
    
    if os_name == "Darwin":
        return _install_launchagent(label, command, interval_minutes)
    elif os_name == "Linux":
        return _install_cron(label, command, interval_minutes)
    elif os_name == "Windows":
        return _install_task_scheduler(label, command, interval_minutes)
    else:
        return False


def _install_launchagent(label: str, command: str, interval_minutes: int) -> bool:
    """Install a LaunchAgent on macOS."""
    from pathlib import Path
    
    agents_dir = Path.home() / "Library" / "LaunchAgents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    
    plist_path = agents_dir / f"com.keel.{label}.plist"
    
    # Convert command to run at intervals (in seconds)
    interval_seconds = interval_minutes * 60
    
    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.keel.{label}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/sh</string>
        <string>-c</string>
        <string>{command}</string>
    </array>
    <key>StartInterval</key>
    <integer>{interval_seconds}</integer>
    <key>StandardOutPath</key>
    <string>{get_keel_home() / f"{label}.log"}</string>
    <key>StandardErrorPath</key>
    <string>{get_keel_home() / f"{label}.err"}</string>
</dict>
</plist>"""
    
    try:
        plist_path.write_text(plist_content)
        # Load the agent
        subprocess.run(["launchctl", "load", str(plist_path)], check=False)
        return True
    except Exception as e:
        print(f"Error installing LaunchAgent: {e}")
        return False


def _install_cron(label: str, command: str, interval_minutes: int) -> bool:
    """Install a cron job on Linux."""
    try:
        # Read current crontab
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
        )
        existing_crons = result.stdout if result.returncode == 0 else ""
        
        # Create cron entry
        cron_interval = f"*/{interval_minutes}" if interval_minutes < 60 else "*"
        cron_hour = "*"
        cron_entry = f"{cron_interval % 60} {cron_hour} * * * {command}\n"
        
        # Check if already installed (simple check)
        if label in existing_crons:
            return True
        
        # Append new entry
        new_crons = existing_crons.rstrip() + "\n" + f"# keel: {label}\n" + cron_entry
        
        # Write back to crontab
        process = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
        process.communicate(input=new_crons)
        
        return process.returncode == 0
    except Exception as e:
        print(f"Error installing cron: {e}")
        return False


def _install_task_scheduler(label: str, command: str, interval_minutes: int) -> bool:
    """Install a Windows Task Scheduler job."""
    try:
        # PowerShell command to create a scheduled task
        ps_command = f"""
        $taskName = 'keel-{label}'
        $action = New-ScheduledTaskAction -Execute 'python' -Argument '{command}'
        $trigger = New-ScheduledTaskTrigger -RepetitionInterval (New-TimeSpan -Minutes {interval_minutes}) -At (Get-Date)
        $principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -RunLevel Limited
        Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Principal $principal -Force
        """
        
        result = subprocess.run(
            ["powershell", "-Command", ps_command],
            capture_output=True,
            text=True,
        )
        
        return result.returncode == 0
    except Exception as e:
        print(f"Error installing Task Scheduler job: {e}")
        return False


def remove_cron_job(label: str) -> bool:
    """Remove a scheduled job (OS-specific).
    
    Args:
        label: The label used when installing the job
    
    Returns:
        True if successful or job didn't exist, False on error
    """
    os_name = get_os()
    
    if os_name == "Darwin":
        return _remove_launchagent(label)
    elif os_name == "Linux":
        return _remove_cron(label)
    elif os_name == "Windows":
        return _remove_task_scheduler(label)
    else:
        return False


def _remove_launchagent(label: str) -> bool:
    """Remove a LaunchAgent on macOS."""
    agents_dir = Path.home() / "Library" / "LaunchAgents"
    plist_path = agents_dir / f"com.keel.{label}.plist"
    
    try:
        if plist_path.exists():
            subprocess.run(["launchctl", "unload", str(plist_path)], check=False)
            plist_path.unlink()
        return True
    except Exception as e:
        print(f"Error removing LaunchAgent: {e}")
        return False


def _remove_cron(label: str) -> bool:
    """Remove a cron job on Linux."""
    try:
        result = subprocess.run(
            ["crontab", "-l"],
            capture_output=True,
            text=True,
        )
        existing_crons = result.stdout if result.returncode == 0 else ""
        
        # Filter out lines related to this label
        new_crons = "\n".join(
            line for line in existing_crons.split("\n")
            if label not in line
        )
        
        process = subprocess.Popen(["crontab", "-"], stdin=subprocess.PIPE, text=True)
        process.communicate(input=new_crons)
        
        return process.returncode == 0
    except Exception as e:
        print(f"Error removing cron job: {e}")
        return False


def _remove_task_scheduler(label: str) -> bool:
    """Remove a Windows Task Scheduler job."""
    try:
        subprocess.run(
            ["powershell", "-Command", f"Unregister-ScheduledTask -TaskName 'keel-{label}' -Confirm:$false"],
            capture_output=True,
        )
        return True
    except Exception as e:
        print(f"Error removing Task Scheduler job: {e}")
        return False


def which(command: str) -> Optional[Path]:
    """Find a command in PATH (cross-platform).
    
    Args:
        command: Command name to find (e.g., 'python3', 'git')
    
    Returns:
        Path to the command if found, None otherwise
    """
    result = subprocess.run(
        ["where" if get_os() == "Windows" else "which", command],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return Path(result.stdout.strip().split("\n")[0])
    return None
