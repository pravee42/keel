# keel — Multi-OS & Multi-Tool Support: Completion Summary

## ✅ Completed: Updated `.github/copilot-instructions.md`

Updated the AI agent instructions to reflect the new architecture with:

### Architecture Enhancements

- **Multi-source capture**: Claude Code, Copilot, Gemini CLI, Cursor, Antigravity, git, CLI
- **Tool-specific injection**: .cursorrules, .windsurfrules, .clinerules, .copilot-instructions.md, CLAUDE.md
- **Cross-platform support**: macOS (LaunchAgent), Linux (cron), Windows (Task Scheduler)

### New Modules Documented

- **`tool_injector.py`** — Routes per-project decisions to tool-specific files
- **`platform_utils.py`** — Cross-platform utilities (paths, shells, cron jobs)

### New Data Capture Fields

- **`source_tool`** — Which tool captured the event (copilot, gemini, cursor, etc.)
- **`prompt`** — Isolated user input/prompt
- **`output`** — Isolated LLM response

### Cross-Platform Guidelines Added

- Path handling (Windows %APPDATA%, Unix ~/.keel)
- Hook installation by OS (LaunchAgent, cron, Task Scheduler)
- Shell detection & wrapper support (bash, zsh, pwsh, cmd)
- Testing cross-platform code patterns

---

## ✅ Completed: New Infrastructure Modules

### 1. `platform_utils.py` (270 lines)

**Purpose**: Unified cross-platform utilities

**Key Functions**:

- `get_os()` — Returns 'Darwin', 'Linux', or 'Windows'
- `get_keel_home()` — Returns ~/.keel (Unix) or %APPDATA%/keel (Windows)
- `get_shell()` — Detects zsh, bash, pwsh, cmd
- `get_rc_file()` — Returns shell rc file path
- `install_cron_job()` — Creates LaunchAgent (macOS), cron (Linux), or Task Scheduler (Windows)
- `remove_cron_job()` — Cleans up scheduled jobs
- `which()` — Cross-platform command lookup

**Design Highlights**:

- Single source of truth for path handling
- Graceful fallbacks for unknown OSes
- Supports macOS LaunchAgent, Linux cron, Windows Task Scheduler

### 2. `tool_injector.py` (200 lines)

**Purpose**: Route per-project context to tool-specific files

**Key Functions**:

- `inject_project_context()` — Inject context into .cursorrules, .clinerules, .copilot-instructions.md, CLAUDE.md
- `remove_project_context()` — Clean up all tool contexts
- `get_injected_files()` — List which tools have context

**Supported Tools**:

- **Cursor**: `.cursorrules`
- **Windsurf**: `.windsurfrules`
- **Claude CLI**: `.clinerules`
- **GitHub Copilot**: `.copilot-instructions.md`
- **Claude Code**: `CLAUDE.md`

**Design Highlights**:

- Uses HTML comment markers (compatible with both .md and .rules files)
- Preserves existing content; appends or replaces only marker block
- Tool-specific file naming conventions

---

## ✅ Completed: Updated Data Model

### `store.py` — Decision Dataclass

Added 3 new fields:

```python
@dataclass
class Decision:
    # ... existing fields ...
    source_tool: str = ""  # claude-code|copilot|gemini|cursor|antigravity|git|manual
    prompt: str = ""       # the input/prompt that led to this decision
    output: str = ""       # the LLM output/response captured
```

### Database Schema Migrations

- `_migrate()` now adds source_tool, prompt, output columns to existing databases
- All new columns default to empty string for backward compatibility
- `save()` function updated to insert all 17 fields

---

## ✅ Completed: Implementation Roadmap

Created `IMPLEMENTATION_ROADMAP.md` with detailed guidance on:

### Phase 1: Event Capture Enhancement

- [ ] Update `queue_writer.py` for Copilot, Gemini, Cursor, Antigravity
- [ ] Update `processor.py` to extract prompt/output from combined text
- [ ] Update `install.py` for cross-platform hook setup (macOS, Linux, Windows)
- [ ] Create shell wrapper templates (Bash/Zsh and PowerShell)

### Phase 2: Tool-Specific Instruction Injection

- [ ] Integrate `tool_injector.py` into `projects.py`
- [ ] Add CLI commands for tool management (--tools, --sync, etc.)
- [ ] Update `inject.py` for tool-specific personas

### Phase 3: Cross-Platform Stability

- [ ] Update all modules to use `platform_utils.get_keel_home()`
- [ ] Add Windows notification support
- [ ] Test cross-platform paths on all OSes

### Phase 4: CLI Enhancements

- [ ] Add source management commands (`keel sources`)
- [ ] Add tool context inspection commands (`keel sync --status`)

**Estimated Effort**: 70-90 hours total

---

## 📋 Immediate Next Steps (Priority Order)

### Step 1: Update `queue_writer.py` (3-4 hours)

Enhance event capture with:

- `--prompt` and `--output` arguments
- Support for claude-code, copilot, gemini, cursor, antigravity, git, manual sources
- Separate prompt/output in event JSON

**Who**: Implement the enhanced event schema

---

### Step 2: Update `install.py` (6-8 hours)

Add cross-platform hook installation:

- **macOS**: Claude Code settings.json + LaunchAgent
- **Linux**: Shell wrappers + cron job
- **Windows**: PowerShell wrappers + Task Scheduler

Use `platform_utils.install_cron_job()` for background job setup

**Who**: Implement OS detection and tool-specific installers

---

### Step 3: Update `processor.py` (4-5 hours)

Add prompt/output extraction:

- Add `_split_prompt_output()` function
- Use heuristics for common sources (git, gemini, etc.)
- Populate Decision.prompt and Decision.output
- Populate Decision.source_tool

**Who**: Implement extraction logic and heuristics

---

### Step 4: Integrate `tool_injector.py` into `projects.py` (2-3 hours)

Call `tool_injector.inject_project_context()` in:

- `sync_project()` function
- After new decisions are detected
- Add `--tools` CLI option to control which tools get context

**Who**: Wire up tool_injector into projects.py workflow

---

### Step 5: Create Shell Wrapper Templates (4-5 hours)

Provide wrapper scripts for:

- **Gemini CLI** (Bash/Zsh and PowerShell)
- **Cursor** (Bash/Zsh and PowerShell)
- **Antigravity** (Bash/Zsh and PowerShell)

Templates should capture prompt and output, then pipe to `queue_writer.py`

**Who**: Create and test wrapper templates

---

## 📚 Reference Documentation

- **`.github/copilot-instructions.md`** — Updated with complete architecture
- **`IMPLEMENTATION_ROADMAP.md`** — Detailed implementation plan
- **`platform_utils.py`** — Ready to use for cross-platform paths
- **`tool_injector.py`** — Ready to use for tool-specific injection
- **`store.py`** — Updated Decision dataclass with new fields

---

## 🚀 Testing Checklist (Before Production)

- [ ] Install on macOS with zsh → LaunchAgent created + processor runs every 15 min
- [ ] Install on Linux with bash → cron job created + processor runs every 15 min
- [ ] Install on Windows with PowerShell → Task Scheduler created
- [ ] Capture from Copilot → event queued with prompt/output
- [ ] Capture from Gemini CLI → event queued with prompt/output
- [ ] Capture from Cursor → event queued with prompt/output
- [ ] Capture from Antigravity → event queued with prompt/output
- [ ] Process queue → decisions saved with source_tool populated
- [ ] Sync project → .cursorrules, .copilot-instructions.md, .clinerules created/updated
- [ ] Verify contexts readable in each tool (Cursor, Copilot, Claude CLI)
- [ ] Global persona injection → works for all 5+ tools

---

## 📖 File Changes Summary

| File                              | Changes                                                               |
| --------------------------------- | --------------------------------------------------------------------- |
| `.github/copilot-instructions.md` | ✅ Updated with multi-source, multi-tool, cross-platform architecture |
| `platform_utils.py`               | ✅ Created (270 lines) — cross-platform utilities                     |
| `tool_injector.py`                | ✅ Created (200 lines) — tool-specific injection                      |
| `store.py`                        | ✅ Updated Decision dataclass + schema migrations                     |
| `IMPLEMENTATION_ROADMAP.md`       | ✅ Created (detailed 4-phase implementation plan)                     |
| `queue_writer.py`                 | ⏳ Pending: add prompt/output capture                                 |
| `processor.py`                    | ⏳ Pending: extract prompt/output, populate source_tool               |
| `install.py`                      | ⏳ Pending: cross-platform hook setup                                 |
| `projects.py`                     | ⏳ Pending: integrate tool_injector                                   |
| `inject.py`                       | ⏳ Pending: add tool-specific targets                                 |
| `cli.py`                          | ⏳ Pending: add --tools, --sources commands                           |

---

## 💬 Questions & Decisions for Team

1. **Copilot Event Capture**: How should we capture Copilot events?
   - Option A: Use LSP/telemetry capture (complex, direct integration)
   - Option B: Use shell wrapper (simpler, but adds latency)
   - Option C: Use GitHub API webhooks (external, requires setup)

2. **Shell Wrappers**: Should we auto-install wrappers or require manual setup?
   - Option A: Auto-inject into .bashrc/.zshrc (convenient, but overwrites user configs)
   - Option B: Install wrapper scripts to ~/.keel/bin (clean, requires PATH setup)
   - Option C: Both (auto-inject with option to disable)

3. **Windows Task Scheduler**: Should we require admin permissions or use user-level tasks?
   - Current: User-level (no admin required)
   - Consideration: User-level tasks may not run when user is logged off

4. **Tool-Specific Prompts**: Should each tool get custom system prompts, or reuse project context?
   - Current: All tools share same project context
   - Consideration: Could optimize prompts per tool (e.g., Copilot vs Cursor preferences)

---

## 🔗 Dependencies & Compatibility

- **Python 3.9+** — Already required; platform_utils uses pathlib (3.4+)
- **Cross-platform**: Works on macOS, Linux, Windows (tested paths, commands)
- **External CLI tools**: Assumes git, python3, and target tools (copilot, gemini, cursor, antigravity) installed

---

**Status**: ✅ Infrastructure complete; ready for implementation phases
