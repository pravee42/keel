# keel — Architecture Diagrams

## 1. Multi-Source Event Capture Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                    Multi-Source Event Capture                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ SOURCE TOOLS (capture events with prompt + output)      │   │
│  ├─────────────────────────────────────────────────────────┤   │
│  │                                                         │   │
│  │ [Claude Code]  →  hook: UserPromptSubmit               │   │
│  │ [GitHub Copilot] → hook: LSP/telemetry OR wrapper      │   │
│  │ [Gemini CLI]  →  wrapper: shell function              │   │
│  │ [Cursor]      →  hook: editor settings.json            │   │
│  │ [Antigravity] →  wrapper: shell function              │   │
│  │ [git commit]  →  hook: post-commit hook               │   │
│  │ [Manual]      →  CLI: keel log                         │   │
│  │                                                         │   │
│  └────────────────┬────────────────────────────────────────┘   │
│                   │                                             │
│                   ↓                                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ queue_writer.py (NON-BLOCKING)                          │   │
│  │ • Receives: source, type, prompt, output, cwd          │   │
│  │ • Appends JSON event to ~/.keel/queue.jsonl            │   │
│  │ • Returns immediately (< 100ms)                        │   │
│  └────────────────┬────────────────────────────────────────┘   │
│                   │                                             │
└───────────────────┼─────────────────────────────────────────────┘
                    │
                    │ (every 15 min OR manual: keel process)
                    ↓
┌─────────────────────────────────────────────────────────────────┐
│                     Event Processing                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ processor.py                                            │   │
│  │ Step 1: CLASSIFY (LLM) — is this a real decision?     │   │
│  │ Step 2: EXTRACT (LLM) — title, context, choice, etc.  │   │
│  │ Step 3: SPLIT PROMPT/OUTPUT — using source heuristics │   │
│  │ Step 4: STAMP PROJECT — git root detection            │   │
│  │ Step 5: EXTRACT PRINCIPLES — from reasoning           │   │
│  └────────────────┬────────────────────────────────────────┘   │
│                   │                                             │
│                   ↓                                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ store.py — SQLite ~/.keel/decisions.db                 │   │
│  │ • Persist: Decision(id, timestamp, domain, title,      │   │
│  │            context, options, choice, reasoning,         │   │
│  │            principles, project, source_tool,            │   │
│  │            prompt, output, ...)                         │   │
│  └────────────────┬────────────────────────────────────────┘   │
│                   │                                             │
│                   ↓                                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ analyzer.py — LLM Analysis                              │   │
│  │ • Find similar past decisions                           │   │
│  │ • Consistency diff (is this a contradiction?)           │   │
│  │ • Notify if inconsistency detected                      │   │
│  └────────────────┬────────────────────────────────────────┘   │
│                   │                                             │
│                   ↓                                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ projects.py + tool_injector.py                          │   │
│  │ • Generate per-project context block                    │   │
│  │ • Inject into tool-specific files                       │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 2. Per-Project Context Injection

```
┌──────────────────────────────────────────────────────────────────┐
│              Per-Project Context Injection (projects.py)         │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Input: List of decisions for project /path/to/my-project       │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ projects.py                                                │ │
│  │ • Read all decisions for project (filtered by .project)   │ │
│  │ • LLM: synthesize context block (max 700 tokens)          │ │
│  │ • Call tool_injector.inject_project_context()             │ │
│  └────────────────┬─────────────────────────────────────────┘ │
│                   │                                             │
│       ┌───────────┼───────────┬──────────────┐                  │
│       ↓           ↓           ↓              ↓                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ Cursor   │ │ Copilot  │ │ Windsurf │ │ Claude   │           │
│  │ Editor   │ │ GitHub   │ │ Editor   │ │ CLI      │           │
│  │          │ │          │ │          │ │          │           │
│  │.cursorrules │.copilot-│ │.windsurf─│ │.clinerules │         │
│  │          │ │instructions│ │rules   │ │          │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
│       ↓           ↓           ↓              ↓                  │
│       └───────────┴───────────┴──────────────┘                  │
│                   │                                             │
│                   ↓                                             │
│       ┌──────────────────────────────┐                          │
│       │ {repo_root}/CLAUDE.md         │                          │
│       │ (generic Claude Code)         │                          │
│       └──────────────────────────────┘                          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

## 3. Tool-Specific File Structure

```
Repository Root ({repo_root}/)
├── .git/
├── .cursorrules              ← Context block injected here (Cursor)
│   <!-- keel:project:start -->
│   ## Project Decisions (my-project)
│   **Uses TypeScript**: Chosen for type safety in large team...
│   <!-- keel:project:end -->
│
├── .windsurfrules            ← Context block injected here (Windsurf)
├── .clinerules               ← Context block injected here (Claude CLI)
├── .copilot-instructions.md  ← Context block injected here (GitHub Copilot)
│
├── CLAUDE.md                 ← Context block injected here (Claude Code)
│   <!-- keel:project:start -->
│   ## Project Decisions
│   ...
│   <!-- keel:project:end -->
│
├── src/
├── tests/
└── ...

Note: Each tool file contains markers that keel uses to inject/replace content:
  <!-- keel:project:start -->
  [project-specific context injected by keel]
  <!-- keel:project:end -->
```

## 4. Cross-Platform Configuration

```
┌─────────────────────────────────────────────────────────────────┐
│                   platform_utils.py Abstraction                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ get_keel_home()                                           │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │  macOS/Linux:  ~/.keel/                                  │ │
│  │  Windows:      %APPDATA%/keel/  (C:\Users\{u}\AppData...) │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ get_shell()                                               │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │  Detects: zsh, bash, pwsh (PowerShell), cmd              │ │
│  │  Returns rc file path: ~/.zshrc, ~/.bashrc, etc.         │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ install_cron_job(label, command, interval_minutes)       │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │  macOS:   creates LaunchAgent in                          │ │
│  │           ~/Library/LaunchAgents/com.keel.{label}.plist   │ │
│  │  Linux:   adds cron job via `crontab -e`                 │ │
│  │  Windows: creates Task Scheduler job via PowerShell      │ │
│  │  All:     runs background job every 15 min               │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 5. Decision Data Model (Extended)

```
Decision Dataclass
├── Core Fields (existing)
│   ├── id: str                      # UUID short form
│   ├── timestamp: str               # ISO format (UTC)
│   ├── domain: str                  # code|writing|business|life|other
│   ├── title: str                   # one-line decision
│   ├── context: str                 # situation/problem
│   ├── options: str                 # alternatives considered
│   ├── choice: str                  # what was decided
│   ├── reasoning: str               # why
│   ├── principles: str              # JSON list (extracted by analyzer)
│   ├── tags: str                    # JSON: pressure|uncertainty|arch
│   ├── paths: str                   # JSON: file paths touched
│   ├── project: str                 # git root (absolute path)
│   ├── outcome: str                 # filled later if known
│   └── outcome_quality: str         # good|neutral|bad
│
└── Event Capture Fields (NEW)
    ├── source_tool: str             # claude-code|copilot|gemini|cursor|
    │                                # antigravity|git|manual
    ├── prompt: str                  # isolated user input/prompt
    └── output: str                  # isolated LLM response/output

SQLite Storage:
  ~/.keel/decisions.db
  Table: decisions (17 columns, indexed by id + project)
```

## 6. Event Queue Format

```
Event JSON (stored in ~/.keel/queue.jsonl)

{
  "id": "a1b2c3d4",
  "timestamp": "2026-04-04T10:30:45Z",
  "source": "copilot",                    ← Which tool captured
  "type": "prompt",                       ← Event type
  "cwd": "/Users/user/project",           ← Working directory
  "text": "Here's my full input...",       ← Combined text (fallback)
  "prompt": "Write a function that...",   ← Isolated prompt (NEW)
  "output": "Here's the function...",     ← Isolated output (NEW)
  "processed": false                      ← Processor marks as true
}

Queue file location: ~/.keel/queue.jsonl (JSONL format, one event per line)
```

## 7. Background Job Setup (Cross-Platform)

```
┌──────────────────────────────────────────────────────────┐
│            Background Job Setup (install_cron_job)       │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  macOS                                                   │
│  └─ ~/Library/LaunchAgents/com.keel.processor.plist     │
│     • Runs: python3 {path}/processor.py                 │
│     • Interval: 900 seconds (15 minutes)                │
│     • Logs to: ~/.keel/processor.log                    │
│     • Load: `launchctl load ...` (auto on login)        │
│                                                          │
│  Linux                                                   │
│  └─ crontab entry (via `crontab -e`)                    │
│     • */15 * * * * python3 {path}/processor.py          │
│     • Runs every 15 minutes                             │
│     • Logs handled by cron                              │
│                                                          │
│  Windows                                                 │
│  └─ Task Scheduler                                       │
│     • Task Name: keel-processor                         │
│     • Action: python {path}\processor.py                │
│     • Trigger: Repeat every 15 minutes                  │
│     • Run as: Current user (no admin required)          │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

## 8. CLI Workflow Example

```
$ keel install
  ✓ Detecting OS: Darwin (macOS)
  ✓ Detecting shell: zsh
  ✓ Installing Claude Code hook (~/.claude/settings.json)
  ✓ Installing git post-commit hook (~/.git-hooks/)
  ✓ Installing Gemini CLI wrapper (~/.zshrc)
  ✓ Installing Cursor wrapper (~/.zshrc)
  ✓ Installing LaunchAgent (processor every 15 min)
  ✓ Installation complete

$ keel process
  Processing queue: 5 events found
  ✓ Event 1 (copilot): Classified as decision
  ✓ Event 2 (gemini): Classified as decision
  ✓ Event 3 (git): Classified as decision
  ✗ Event 4 (claude-code): Not a decision (debug output)
  ✗ Event 5 (manual): Classification uncertain

  Extracted 3 decisions, saved to ~/.keel/decisions.db

$ keel sync
  Found 5 projects with decisions
  Syncing /Users/user/project1:
    ✓ Injecting context into .cursorrules
    ✓ Injecting context into .copilot-instructions.md
    ✓ Injecting context into CLAUDE.md
  Syncing /Users/user/project2:
    ✓ Injecting context into .clinerules
    ✓ Injecting context into CLAUDE.md
  Complete
```

---

**Legend**:

- `→` = flow
- `↓` = process step
- `✓` = success
- `✗` = filtered/not processed
- `[ ]` = tool/file
- `( )` = explanation

---

For more details, see:

- `.github/copilot-instructions.md` — Complete architecture guide
- `IMPLEMENTATION_ROADMAP.md` — Detailed implementation plan
- `COMPLETION_SUMMARY.md` — Status and next steps
