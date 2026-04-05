# GEMINI.md — keel

## Project Overview
**keel** is a passive decision-tracking tool for software engineers. It acts as a "git diff for your thinking" by watching AI coding sessions (Claude Code, Gemini CLI, etc.) and git commits, extracting the architectural and strategic decisions buried within them, and learning your judgment style over time.

### Key Features:
- **Passive Capture:** Hooks into Claude Code, Git, Gemini CLI, and other tools via shell wrappers and a local OpenAI-compatible proxy.
- **Decision Extraction:** Uses LLMs to classify events and extract structured data (title, context, options, choice, reasoning, and principles).
- **Consistency Checking:** Flags when a new decision contradicts past reasoning.
- **Developer Persona:** Synthesizes a "developer identity document" (persona.md) from your decision history.
- **Context Injection:** Automatically injects per-project context into `CLAUDE.md` to keep AI agents aligned with existing project decisions.
- **Outcome Analysis:** Tracks the quality of decision outcomes to identify which principles are most effective.
- **Team Mode:** Allows sharing and comparing decision histories with teammates.

### Architecture:
- **Core Logic:** `cli.py` (CLI), `processor.py` (Queue processing), `analyzer.py` (LLM analysis), `llm.py` (Unified client).
- **Storage:** SQLite database at `~/.keel/decisions.db`.
- **Hooks:** Lightweight `queue_writer.py` appends raw events to `~/.keel/queue.jsonl`.
- **Automation:** macOS LaunchAgents (or cron) run background tasks for processing, profiling, and syncing.
- **UI:** Flask-based web server (`webserver.py`) with a dashboard for exploring decisions and metrics.

---

## Building and Running

### Prerequisites:
- Python 3.9+ (optimized for macOS system default)
- Active internet connection for LLM API calls (Anthropic, OpenAI, Gemini, etc.)

### Setup:
```bash
# Install dependencies
pip install -r requirements.txt

# Configure your LLM provider
keel config provider anthropic
keel config key anthropic <your-key>

# Install hooks and background services
keel install
keel service install
```

### Key Commands:
- `keel ls`: List all tracked decisions.
- `keel process`: Manually trigger the queue processor.
- `keel sync`: Sync project-specific context into `CLAUDE.md`.
- `keel profile --build`: Rebuild your developer persona.
- `keel web`: Start the local web dashboard.
- `keel cost`: View token usage and estimated spend.

---

## Development Conventions

### Coding Style:
- **Python 3.9 Compatibility:** Avoid `X | Y` union syntax; use `Optional[X]` from `typing`.
- **Type Hinting:** Use type hints for all function signatures and complex variables.
- **LLM Abstraction:** Never call LLM providers directly; always use the `llm.complete()` or `llm.stream_complete()` methods in `llm.py`.
- **Data Privacy:** All persistent data must be stored in `~/.keel/`. Never write runtime data to the project repository.

### Testing Practices:
- **Reproduction First:** When fixing bugs, create a reproduction script or test case first.
- **Validation:** Always verify changes by running relevant CLI commands and checking the SQLite database state.

### Contribution Guidelines:
- **Conventional Commits:** Use standard prefixes like `feat:`, `fix:`, `refactor:`, `chore:`.
- **Non-Blocking Hooks:** Ensure that any changes to `queue_writer.py` remain extremely lightweight and fast, as it runs on every prompt.
- **Documentation:** Keep `ARCHITECTURE.md` and `CLAUDE.md` updated with significant architectural shifts.
