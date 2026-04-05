# keel — Implementation Roadmap for Multi-OS & Multi-Tool Support

## Overview

This document outlines the implementation requirements to extend keel with:

1. **Multi-source event capture** (Copilot, Gemini CLI, Cursor, Antigravity) with prompt/output logging
2. **Tool-specific memory injection** (.cursorrules, .clinerules, .copilot-instructions.md, etc.)
3. **Cross-platform support** (Windows, Linux, macOS)

## Completed Infrastructure

### New Modules Created

#### `platform_utils.py` ✅

- **Purpose**: Unified cross-platform utilities for path resolution, process management, shell detection
- **Key Functions**:
  - `get_keel_home()` — Returns `~/.keel/` (Unix) or `%APPDATA%/keel/` (Windows)
  - `get_shell()` — Detects current shell (zsh, bash, pwsh, cmd)
  - `get_rc_file()` — Returns appropriate rc file path for shell
  - `install_cron_job()` — Installs background jobs (LaunchAgent/cron/Task Scheduler)
  - `which()` — Cross-platform command lookup
  - `remove_cron_job()` — Cleanup scheduled jobs
- **Design**: Abstracts OS-specific behavior; single point for Path handling

#### `tool_injector.py` ✅

- **Purpose**: Route per-project decisions to tool-specific instruction files
- **Key Functions**:
  - `inject_project_context()` — Inject context into specified tools
  - `remove_project_context()` — Clean up injected contexts
  - `get_injected_files()` — List which tools have context injected
- **Design**: Supports 5 tool targets (.cursorrules, .windsurfrules, .clinerules, .copilot-instructions.md, CLAUDE.md)

### Updated Data Model

#### `store.py` — Decision Dataclass ✅

Added three new fields to capture source and context:

```python
source_tool: str = ""  # claude-code|copilot|gemini|cursor|antigravity|git|manual
prompt: str = ""       # the input/prompt that led to this decision
output: str = ""       # the LLM output/response captured
```

Schema migration handles adding these columns to existing databases.

## Implementation Tasks (Priority Order)

### Phase 1: Event Capture Enhancement (High Priority)

#### 1.1 Update `queue_writer.py` for Multi-Source Support

**Goal**: Enhance event capture for Copilot, Gemini CLI, Cursor, Antigravity

**Changes Needed**:

```python
# Support new source tools
SUPPORTED_SOURCES = {
    "claude-code": "Claude Code",
    "copilot": "GitHub Copilot",
    "gemini": "Gemini CLI",
    "cursor": "Cursor Editor",
    "antigravity": "Antigravity CLI",
    "git": "Git Commit",
    "manual": "Manual Log",
}

# Enhance event structure to capture prompt/output separately
event = {
    "id": str,
    "timestamp": str,
    "source": str,
    "type": str,
    "cwd": str,
    "text": str,           # full text (fallback)
    "prompt": str,        # isolated prompt (if available)
    "output": str,        # isolated output (if available)
    "processed": False,
}
```

**Files to Modify**:

- `queue_writer.py` — Add `--prompt` and `--output` arguments
- CLI tools may need wrapper scripts

#### 1.2 Update `processor.py` to Extract Prompt/Output

**Goal**: Parse combined text into prompt + output where possible

**Implementation Strategy**:

- For git commits: use "---" or empty line as delimiter
- For Gemini/Antigravity: use heuristics (e.g., "User:" vs "Assistant:")
- Fallback: store combined text; processor marks as "full_text_mode"

**Code Pattern**:

```python
def _split_prompt_output(text: str, source: str) -> tuple[str, str]:
    """Split combined text into prompt and output based on source."""
    if source == "git":
        # Split on "COMMIT:\n" delimiter
        pass
    elif source in ("gemini", "antigravity"):
        # Split on "---" or regex pattern
        pass
    # Fallback: return (full_text, "")
```

**Files to Modify**:

- `processor.py` — Add `_split_prompt_output()` function
- Update `extract()` to populate Decision.prompt and Decision.output

#### 1.3 Update `install.py` for Cross-Platform Hook Setup

**Goal**: Auto-install hooks for all 7 sources on all 3 OS

**Implementation Strategy**:

**macOS**:

- Claude Code: settings.json hook (existing)
- Git: global post-commit hook (existing)
- Copilot: LSP/telemetry capture OR shell wrapper
- Gemini CLI: shell wrapper in ~/.zshrc
- Cursor: settings.json hook (if available)
- Antigravity: shell wrapper in ~/.zshrc
- Background: LaunchAgent via `platform_utils.install_cron_job()`

**Linux**:

- Claude Code: N/A (not available)
- Git: global post-commit hook (existing)
- Copilot: shell wrapper
- Gemini CLI: shell wrapper in ~/.bashrc
- Cursor: shell wrapper (if installed)
- Antigravity: shell wrapper in ~/.bashrc
- Background: cron via `platform_utils.install_cron_job()`

**Windows**:

- Claude Code: N/A
- Git: global post-commit hook (PowerShell)
- Copilot: registry hook OR PowerShell wrapper
- Gemini CLI: PowerShell wrapper
- Cursor: registry hook OR PowerShell wrapper
- Antigravity: PowerShell wrapper
- Background: Task Scheduler via `platform_utils.install_cron_job()`

**Code Outline**:

```python
def install_copilot_hook():
    """Platform-specific Copilot event capture."""
    if platform.system() == "Darwin":
        _install_copilot_macos()
    elif platform.system() == "Windows":
        _install_copilot_windows()
    elif platform.system() == "Linux":
        _install_copilot_linux()

def install_shell_wrappers():
    """Add AI CLI wrappers to rc files."""
    shell = platform_utils.get_shell()
    rc_file = platform_utils.get_rc_file()

    wrappers = {
        "gemini": "gemini_wrapper",
        "antigravity": "antigravity_wrapper",
        "cursor": "cursor_wrapper",
    }

    for tool, func_name in wrappers.items():
        if platform_utils.which(tool):
            _inject_shell_function(rc_file, func_name, tool)
```

**Files to Modify**:

- `install.py` — Add platform detection and per-tool installers
- Import `platform_utils` for cross-platform helpers

#### 1.4 Create Shell Wrappers (templates)

**Goal**: Provide shell wrapper templates for tools that don't have built-in hooks

**Example: Gemini CLI wrapper** (~/.zshrc):

```bash
gemini() {
    local prompt="$*"
    local output=$(/usr/local/bin/gemini "$@" 2>&1)
    local status=$?

    # Log to keel
    echo "$output" | python3 {QUEUE_WRITER} \
        --source gemini \
        --type prompt \
        --prompt "$prompt" \
        --output "$output" \
        --cwd "$(pwd)"

    # Show output to user
    echo "$output"
    return $status
}
```

**Files to Create**:

- `templates/shell_wrappers.sh` — Bash/Zsh wrapper templates
- `templates/powershell_wrappers.ps1` — PowerShell wrapper templates

### Phase 2: Tool-Specific Instruction Injection (Medium Priority)

#### 2.1 Integrate `tool_injector.py` into `projects.py`

**Goal**: Route project context to appropriate tool files

**Changes**:

```python
# In projects.py:
import tool_injector

def sync_project(project_root: str, force: bool = False):
    """Sync project context to all tool files."""
    # Generate context (existing)
    context_block = _generate_context_block(project_root, decisions)

    # Inject into all tools
    results = tool_injector.inject_project_context(
        Path(project_root),
        context_block,
        tool_names=None,  # All tools
    )

    # Log results
    for tool, result in results.items():
        if result is True:
            print(f"✓ {tool} context injected")
        else:
            print(f"✗ {tool}: {result}")
```

**Files to Modify**:

- `projects.py` — Call `tool_injector.inject_project_context()`

#### 2.2 Add CLI Commands for Tool Management

**Goal**: Let users control which tools get context injected

**New CLI Commands**:

```bash
keel sync --tools copilot,cursor  # Sync only specific tools
keel sync --tools all             # Sync all tools (default)
keel sync --tools list            # Show which tools have context
keel sync --remove-tool copilot   # Remove context from specific tool
```

**Files to Modify**:

- `cli.py` — Add `--tools` option to `sync` command

#### 2.3 Update `inject.py` for Tool-Specific Personas

**Goal**: Route global persona to tool-specific config files

**Implementation**:

```python
# Current targets (add to existing):
TARGETS = {
    "claude-code-global": {...},
    "gemini": {...},
    "openai": {...},
    "copilot": {  # NEW
        "label": "GitHub Copilot",
        "path": Path.home() / ".copilot" / "instructions.md",
        "description": "Loaded automatically in GitHub Copilot",
    },
    "cursor": {  # NEW
        "label": "Cursor Editor",
        "path": Path.home() / ".cursor" / "rules.md",
    },
    "antigravity": {  # NEW
        "label": "Antigravity CLI",
        "path": Path.home() / ".antigravity" / "system_prompt.md",
    },
}

def inject(targets: Optional[list] = None):
    """Inject persona into selected tools."""
    # Use platform_utils to detect available tools
    available = []
    for tool in targets or list(TARGETS.keys()):
        if platform_utils.which(tool.split("-")[0]):
            available.append(tool)

    # Inject into available tools only
    ...
```

**Files to Modify**:

- `inject.py` — Add new tool targets

### Phase 3: Cross-Platform Stability (Medium Priority)

#### 3.1 Update `config.py` to Use `platform_utils`

**Goal**: Ensure CONFIG_PATH uses cross-platform paths

**Changes**:

```python
# Before:
CONFIG_PATH = Path.home() / ".keel" / "config.json"

# After:
import platform_utils
CONFIG_PATH = platform_utils.get_keel_home() / "config.json"
```

**Files to Modify**:

- `config.py` — Use `platform_utils.get_keel_home()`
- `store.py` — Use `platform_utils.get_keel_home()`
- `processor.py` — Use `platform_utils.get_keel_home()`
- All modules that reference `~/.keel/`

#### 3.2 Add Windows Notification Support

**Goal**: Show alerts on Windows when contradictions detected

**Current Implementation**: macOS `osascript` notifications only

**New Implementation**:

```python
def notify(title: str, message: str):
    """Cross-platform notification."""
    os_name = platform.system()

    if os_name == "Darwin":
        # Existing osascript
        _notify_macos(title, message)
    elif os_name == "Windows":
        _notify_windows(title, message)
    elif os_name == "Linux":
        _notify_linux(title, message)

def _notify_windows(title: str, message: str):
    """Use PowerShell Toast notification."""
    import subprocess
    ps_cmd = f"""
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

    $APP_ID = "Keel"
    $template = @"
    <toast>
        <visual>
            <binding template="ToastText02">
                <text id="1">{title}</text>
                <text id="2">{message}</text>
            </binding>
        </visual>
    </toast>
    "@

    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml($template)
    $toast = New-Object Windows.UI.Notifications.ToastNotification $xml
    [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($APP_ID).Show($toast)
    """
    subprocess.run(["powershell", "-Command", ps_cmd], capture_output=True)
```

**Files to Modify** (or create new):

- `notifications.py` — New module for cross-platform notifications
- Existing notification callers to use new module

#### 3.3 Test Cross-Platform Paths

**Goal**: Validate that all paths work on all OSes

**Test Checklist**:

- [ ] `platform_utils.get_keel_home()` returns correct paths on all OSes
- [ ] `Path` operations use forward slashes (or `pathlib` handles it)
- [ ] Shell detection works on bash, zsh, pwsh, cmd
- [ ] Config file read/write works with Windows paths
- [ ] SQLite DB path works with Windows
- [ ] Git root detection works on all OSes (`git rev-parse --show-toplevel`)

**Files to Test**:

- Run on Windows, Linux, macOS with different shells

### Phase 4: CLI Enhancements (Low Priority)

#### 4.1 Add Commands for Multi-Source Management

**Goal**: User-friendly commands to inspect and manage sources

**New Commands**:

```bash
keel sources                      # List all configured sources
keel sources --test               # Test all sources
keel sources copilot --test       # Test specific source
keel sources gemini --install     # Install/update gemini wrapper
keel sources --disable copilot    # Disable event capture for tool
```

**Files to Modify**:

- `cli.py` — Add new `sources` command group

#### 4.2 Add Commands for Tool Context Inspection

**Goal**: Debug which contexts are injected where

**New Commands**:

```bash
keel sync --status                # Show sync status for all projects
keel sync {project_path} --tools  # List injected tools for project
keel context --list               # Show all per-project contexts
```

**Files to Modify**:

- `cli.py` — Add new subcommands

## Testing Strategy

### Unit Tests

- `test_platform_utils.py` — Path resolution on all OSes
- `test_tool_injector.py` — Marker insertion/removal
- `test_store.py` — New Decision fields

### Integration Tests

- `test_install.py` — Hook installation on each OS
- `test_processor.py` — Prompt/output extraction
- `test_projects.py` — Tool-specific context injection

### Manual Testing Checklist

- [ ] Install on macOS → LaunchAgent created
- [ ] Install on Linux → cron job created
- [ ] Install on Windows → Task Scheduler created
- [ ] Capture from Copilot → event in queue
- [ ] Capture from Gemini → event in queue
- [ ] Capture from Cursor → event in queue
- [ ] Process → decision saved with source_tool, prompt, output
- [ ] Sync → .cursorrules, .copilot-instructions.md created
- [ ] Verify context readable in each tool

## Implementation Timeline Estimate

| Phase     | Tasks                       | Estimated Effort |
| --------- | --------------------------- | ---------------- |
| 1         | Event capture enhancement   | 20-30 hrs        |
| 2         | Tool-specific injection     | 10-15 hrs        |
| 3         | Cross-platform stability    | 15-20 hrs        |
| 4         | CLI enhancements            | 5-10 hrs         |
| Testing   | Unit + integration + manual | 10-15 hrs        |
| **Total** |                             | **70-90 hrs**    |

## Documentation Updates Needed

1. Update README.md with new source tools and platform support
2. Update CLAUDE.md with new architecture
3. Add troubleshooting guide for each OS/shell
4. Add tool setup guide (Copilot, Gemini, Cursor, Antigravity)
5. Update `.github/copilot-instructions.md` (already done)

## Risk Mitigation

- **Risk**: Shell wrappers break on new shell versions
  - _Mitigation_: Extensive testing; keep wrappers simple
- **Risk**: Task Scheduler not reliable on Windows
  - _Mitigation_: Provide manual fallback (scheduled PowerShell)
- **Risk**: Marker collisions if user edits files manually
  - _Mitigation_: Preserve surrounding content; warn on conflicts
- **Risk**: Permission issues on cross-platform file writes
  - _Mitigation_: Check permissions before write; graceful fallback

---

**Next Steps**: Start with Phase 1.1 (queue_writer.py) and Phase 1.3 (install.py cross-platform setup).
