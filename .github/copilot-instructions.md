# keel — AI Agent Coding Instructions

**keel** is a decision-tracking tool that watches AI prompts and git commits to extract architectural decisions, flag contradictions, and sync context into AI tools.

## Architecture at a Glance

```
Multi-Source Event Capture:
  Claude Code / Copilot / Gemini CLI / Cursor / Antigravity / git / CLI
    ↓ (with prompt + output context)
  queue_writer.py (non-blocking JSONL append to ~/.keel/queue.jsonl)
    ↓ (15-min cron or manual: keel process)
  processor.py (classify → extract → analyze)
    ↓
  store.py (SQLite at ~/.keel/decisions.db)
    ↓
  analyzer.py (LLM: similarity, consistency, principles)
    ↓
  projects.py (per-project context injection)
    ↓
  tool_injector.py (Claude Code, Copilot, Gemini, Cursor, Antigravity)
    ├─ {repo}/.cursorrules (Cursor-specific)
    ├─ {repo}/.windsurfrules (Windsurf-specific)
    ├─ {repo}/.clinerules (Claude CLI-specific)
    ├─ {repo}/.copilot-instructions.md (GitHub Copilot-specific)
    └─ {repo}/CLAUDE.md (generic Claude Code)
```

### Key Files & Responsibilities

- **`llm.py`** — Unified LLM client routing (Anthropic/OpenAI/OpenRouter/Gemini/Mistral). All LLM calls go through `llm.complete()` or `llm.stream_complete()`, never import SDKs directly.
- **`processor.py`** — Queue processor: classifies events (is this a real decision?), extracts structured fields (title, context, options, choice, reasoning), runs consistency checks, notifies on contradictions.
- **`store.py`** — SQLite schema (Decision dataclass with domain, principles, tags, outcome_quality, source_tool, prompt, output). Use `store.save()`, `store.get_by_id()`, etc. — never raw SQL outside this module.
- **`analyzer.py`** — LLM analysis: extracts principles, finds similar decisions, computes consistency diffs (quotes reasoning, explains if shift is context-driven or contradictory).
- **`config.py`** — Provider/model/key config stored at `~/.keel/config.json`. Supports anthropic/openai/openrouter/gemini/mistral with per-provider defaults. Cross-platform path handling.
- **`projects.py`** — Per-project context generation + injection into tool-specific files (CLAUDE.md, .cursorrules, .copilot-instructions.md, etc.) using tool-specific markers.
- **`tool_injector.py`** (NEW) — Routes per-project decisions to the correct instruction file based on tool context.
- **`inject.py`** — Injects global persona into `~/.claude/CLAUDE.md`, `~/.copilot/instructions.md`, `~/.gemini/system_prompt.md` etc. using markers `<!-- decide:persona:start/end -->`.
- **`queue_writer.py`** — Lightweight hook script (called on every prompt from Copilot, Gemini, Cursor, Antigravity, Claude Code, git). Appends JSON events to `~/.keel/queue.jsonl` with prompt/output context. Must stay fast; no heavy computation here.
- **`install.py`** — Cross-platform hook installer. Detects OS (Windows, Linux, macOS) and sets up appropriate hooks for each tool.
- **`webserver.py`** — Flask GUI (10 pages: dashboard, decisions, process queue, regret, cost, quality, team, reviews, ADRs, GitHub). SSE streaming for real-time updates.
- **`cli.py`** — Typer CLI entry point. Commands map to backend modules (e.g., `keel log`, `keel process`, `keel sync`, `keel profile`).
- **`platform_utils.py`** (NEW) — Cross-platform utilities: path resolution (handles Windows %APPDATA%, Linux ~/.config, macOS ~/), process management, shell detection.

## Critical Patterns & Conventions

### All LLM Calls Must Route Through `llm.py`

- Use `llm.complete()` for JSON extractions (CLASSIFIER_PROMPT, EXTRACTOR_PROMPT, principle extraction).
- Use `llm.stream_complete()` for longer analysis (consistency_diff, digest, profile synthesis).
- Pass `max_tokens=<int>` explicitly.
- Catch exceptions gracefully; LLM calls can fail (rate limits, API errors).
- **Never import anthropic/openai/openrouter/gemini/mistral SDKs outside `llm.py`.**

### Data Model: The Decision Dataclass

```python
@dataclass
class Decision:
    id: str                    # UUID short form
    timestamp: str             # ISO format
    domain: str                # code|writing|business|life|other
    title: str                 # one-line decision
    context: str               # situation/problem (why this decision?)
    options: str               # alternatives considered
    choice: str                # what was decided
    reasoning: str             # why (principles, tradeoffs)
    principles: str            # JSON list, extracted by analyzer
    outcome: str               # filled in later if decision quality known
    tags: str                  # JSON list: pressure|uncertainty|compromise|temporary|arch
    paths: str                 # JSON list: file paths this touches
    project: str               # absolute git root (stamped by processor)
    outcome_quality: str       # good|neutral|bad (filled later)
    source_tool: str           # claude-code|copilot|gemini|cursor|antigravity|git|manual
    prompt: str                # the prompt/input that led to decision
    output: str                # the LLM output/response captured
```

### JSON Extraction Pattern

- All LLM classification/extraction returns JSON strings — use `_parse_json()` helper in processor.py.
- Always extract with `.find()` and `.rfind()` to ignore trailing content:
  ```python
  start, end = text.find("["), text.rfind("]") + 1
  if start == -1 or end == 0: return fallback
  return json.loads(text[start:end])
  ```
- This tolerates LLM reasoning before/after the JSON.

### File Path & Config Conventions

- **Data lives at ~/.keel/** — never write to project directory at runtime.
  - `~/.keel/queue.jsonl` — raw events
  - `~/.keel/decisions.db` — SQLite store
  - `~/.keel/config.json` — LLM provider/model/keys
  - `~/.keel/personas/` — versioned persona snapshots
  - `~/.keel/projects/` — per-project metadata (staleness, sync status)
- **Cross-platform home paths** — use `platform_utils.get_keel_home()` for `~/.keel/`, never hardcode `Path.home()`.
  - macOS/Linux: `~/.keel/`
  - Windows: `%APPDATA%\keel\` or `~\AppData\Roaming\keel\`
- **Tool-specific instruction files** (per-project):
  - Cursor: `.cursorrules`
  - Windsurf: `.windsurfrules`
  - Claude CLI: `.clinerules`
  - GitHub Copilot: `.copilot-instructions.md`
  - Claude Code: `CLAUDE.md`
- **Git root detection** — processor stamps decisions with absolute `project` path by running `git rev-parse --show-toplevel` from event cwd.
- **API keys** — prefer `~/.keel/config.json` (encrypted is future work). Fallback to env vars (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.).

### Marker System (Multi-Tool Context Injection)

- **Global persona injection** (`inject.py`):
  ```html
  <!-- decide:persona:start -->
  [persona content]
  <!-- decide:persona:end -->
  ```
- **Per-project context by tool** (`tool_injector.py`):
  ```html
  <!-- keel:project:start -->
  [project-specific decisions + cross-project principles]
  <!-- keel:project:end -->
  ```
- **Tool-specific instruction routes**:
  - `.cursorrules` / `.windsurfrules` / `.clinerules` → inject at top/bottom (tool-specific rules format)
  - `.copilot-instructions.md` → inject in markdown sections
  - `CLAUDE.md` → inject in markdown sections
- Use `re.sub()` with `re.DOTALL` to replace between markers. Both global and per-project can coexist in the same file.
- Tool-specific rules files (`.cursorrules`, etc.) may not support markers — fallback to appending or prepending content with comments.

### Staleness & Cron Integration

- **processor.py** runs every 15 min via cron/LaunchAgent/Windows Task Scheduler (OS-specific, or manual `keel process`).
- **profile.py** runs daily at 7am; synthesizes all decisions into persona.md.
- **projects.py** tracks last-sync timestamp in `~/.keel/projects/{slug}.json` to avoid redundant rewrites.
- **tool_injector.py** selects target files based on tool context (detected from `source_tool` field in Decision).
- Use `datetime.fromisoformat()` for timestamp comparisons (decisions are ISO strings).
- **Cross-platform cron setup**: use `install.py` to detect OS and install LaunchAgent (macOS), cron (Linux), or Task Scheduler (Windows).

### Error Handling

- Non-blocking queue writes must not raise (called on every prompt). Wrap in try/except, log to stderr if needed.
- LLM calls should timeout (add to `llm.py` if missing); graceful fallback (e.g., skip principle extraction if LLM fails).
- SQLite migrations use `PRAGMA table_info()` to detect missing columns; add columns if needed in `store._migrate()`.

## Multi-Source Event Capture

### Supported Tools & Sources

- **claude-code** — Claude Code editor extension (hook via settings.json `UserPromptSubmit`)
- **copilot** — GitHub Copilot (hook via LSP / telemetry capture)
- **gemini** — Gemini CLI (shell wrapper in ~/.zshrc / ~/.bashrc)
- **cursor** — Cursor editor (hook configuration similar to Claude Code)
- **antigravity** — Antigravity CLI tool (shell wrapper or direct integration)
- **git** — Git commits (global post-commit hook via ~/.git-hooks/)
- **manual** — Interactive keel log command

### Event Capture Pattern

Each tool-specific integration captures 3 elements:

1. **Source tool** — identifier like `copilot`, `gemini`, `cursor`
2. **Prompt** — the user's input/command/prompt (stored in Decision.prompt)
3. **Output** — the LLM response (stored in Decision.output)

The event JSON structure:

```python
{
    "id": str,           # short UUID
    "timestamp": str,    # ISO format
    "source": str,       # tool identifier
    "type": str,         # "prompt" | "commit" | "message"
    "cwd": str,          # working directory (for git root detection)
    "text": str,         # raw combined text (prompt + output for some tools)
    "prompt": str,       # isolated prompt text (optional, filled by processor if possible)
    "output": str,       # isolated output text (optional, filled by processor if possible)
    "processed": bool,   # false until processor.py handles it
}
```

### Prompt/Output Extraction Strategy

- **For interactive tools** (Copilot, Gemini, Cursor): capture request and response separately at the source.
- **For batch tools** (git, Antigravity): use heuristics in processor.py to split combined text (e.g., split on "---" delimiters).
- **Fallback**: if separation fails, store full text in `text` field; processor skips extraction and uses context heuristics.

### Tool-Specific Installation (install.py)

When `keel install` runs:

1. **macOS/Linux**: detect shell, install shell wrappers in ~/.zshrc / ~/.bashrc, set up LaunchAgent/cron for processor
2. **Windows**: install PowerShell/CMD wrappers, set up Windows Task Scheduler for processor
3. **All OS**: validate hook destinations exist (git global config, Claude Code settings, etc.)
4. **Cross-OS paths**: use `platform_utils.get_keel_home()` to resolve paths correctly

## Workflows & Commands (Developer Mental Model)

| Command                | Flow                                                                                                                                  | Key Files                                 |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| `keel install`         | Cross-platform setup: detect OS, install hooks (Claude Code, git, shell wrappers), schedule processor cron/LaunchAgent/Task Scheduler | `install.py`, `platform_utils.py`         |
| `keel process`         | Process queue: classify → extract (including prompt/output split) → consistency check → notify                                        | `processor.py`, `analyzer.py`, `store.py` |
| `keel sync`            | Regenerate per-project instruction files (CLAUDE.md, .cursorrules, .copilot-instructions.md, etc.) from decisions                     | `projects.py`, `tool_injector.py`         |
| `keel profile --build` | LLM synthesizes all decisions into persona.md                                                                                         | `profile.py`, `analyzer.py`               |
| `keel inject`          | Push persona into tool-specific config files (Claude Code, Copilot, Gemini, Cursor, Antigravity)                                      | `inject.py`                               |
| `keel weekly`          | Generate digest: categorize decisions, surface patterns, flag contradictions                                                          | `digest.py`, `analyzer.py`                |
| `keel log`             | Manual decision logging (interactive prompt)                                                                                          | `cli.py`, `store.py`                      |
| Web GUI: `flask run`   | Browse decisions, regret analysis, cost tracking, quality metrics                                                                     | `webserver.py`, `templates/`              |

## Testing & Debugging

- **Inspect queue**: `cat ~/.keel/queue.jsonl` — raw events before processing.
- **Inspect decisions**: `keel ls` or SQLite: `sqlite3 ~/.keel/decisions.db "SELECT id, title, timestamp FROM decisions;"`
- **Check config**: `keel config` shows current provider/model.
- **Test LLM connection**: `keel config test` pings the API.
- **Web GUI**: `keel web` or `python3 webserver.py` on port 5005.

## Python Version & Dependencies

- **Python 3.9+** (no `X | Y` union syntax; use `Optional[X]` instead).
- **Core deps**: anthropic, openai, typer, rich, flask.
- Check `requirements.txt` and `pyproject.toml` for exact versions.
- Install: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`.

## Common Mistakes to Avoid

1. **Importing LLM SDKs outside `llm.py`** — breaks provider abstraction and testing.
2. **Blocking calls in `queue_writer.py`** — slows down every prompt. Keep it lightweight.
3. **Raw SQL outside `store.py`** — use the Decision dataclass + store functions.
4. **Forgetting to check git root** — processor stamps project path; use this to filter decisions by repo.
5. **Not parsing JSON robustly** — LLMs add reasoning before/after; use `_parse_json()` helper.
6. **Overwriting user's markers** — always check `if MARKER_START in existing` before replacing to preserve surrounding content.
7. **Hardcoding paths** — use `platform_utils.get_keel_home()` and avoid `Path.home() / ".keel"` to ensure Windows compatibility.
8. **Shell-specific assumptions** — detect shell in `install.py` (zsh, bash, PowerShell, cmd) before writing wrappers.
9. **Forgetting source_tool in Decision** — always stamp captured events with their source (copilot, gemini, cursor, etc.) for tool-specific injection.

## Cross-Platform Development Guidelines

### Path Handling

- **Never use**: `Path.home() / ".keel"` or hardcoded `~/.keel`
- **Always use**: `platform_utils.get_keel_home()` which returns:
  - Linux/macOS: `~/.keel/`
  - Windows: `%APPDATA%/keel/` (usually `C:\Users\{user}\AppData\Roaming\keel\`)
- Test on Windows with `%APPDATA%`, Linux with `~/.config`, macOS with `~/`

### Hook Installation by OS

- **macOS**: Use `LaunchAgent` (~/Library/LaunchAgents/) with plist files; processor runs every 15 min
- **Linux**: Use `cron` (crontab -e); processor runs every 15 min via standard cron
- **Windows**: Use `Task Scheduler` (via PowerShell/COM); processor runs every 15 min

### Shell Detection & Wrappers

- Detect shell from `$SHELL` env var or check for `.bashrc`, `.zshrc`, `.profile`
- Support: bash, zsh (macOS/Linux), PowerShell, cmd (Windows)
- For Gemini/Antigravity CLI wrappers: source from appropriate rc file
- Use `shutil.which()` to check if tools exist before installing wrappers

### Testing Cross-Platform Code

- Use `platform.system()` (returns 'Darwin', 'Linux', 'Windows') for OS-specific branches
- Prefer `pathlib.Path` over `os.path` for path operations (handles separators automatically)
- Test with actual Windows paths: `C:\Users\...` (with backslashes, not forward slashes)
