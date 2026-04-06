# keel — CLAUDE.md

## What this project is
A passive decision-tracking tool that watches your AI CLI prompts and git commits, extracts architectural/strategic decisions, and flags when your reasoning contradicts your past self. "git diff for thinking."

## Architecture
```
queue_writer.py   — lightweight hook script, writes raw events to ~/.keel/queue.jsonl
processor.py      — classifies events, extracts decisions, runs consistency checks
analyzer.py       — LLM-powered: principle extraction, similarity search, consistency diff
digest.py         — weekly digest: categorizes decisions, generates narrative
config.py         — LLM provider config stored at ~/.keel/config.json
llm.py            — unified LLM client (Anthropic / OpenAI / OpenRouter / Gemini / Mistral)
store.py          — SQLite store at ~/.keel/decisions.db
install.py        — sets up Claude Code hooks, git global hooks, shell wrappers, cron
cli.py            — Typer CLI entry point
```

## Data flow
```
Claude Code prompt / git commit / gemini CLI call
  → queue_writer.py  (non-blocking, appends to queue.jsonl)
  → processor.py     (cron every 15 min, or `keel process`)
    → llm.classify()          skip if not a real decision
    → llm.extract_decision()  structured fields
    → analyzer.extract_principles()
    → store.save()
    → analyzer.find_similar() + consistency_diff()
    → macOS notification if inconsistency flagged
  → keel weekly    (Sunday 9am cron, or manual)
```

## Supported LLM providers
- `anthropic` — default, supports adaptive thinking for richer analysis
- `openai`     — via OpenAI API
- `openrouter` — access any model via unified key
- `gemini`     — via Google Generative AI OpenAI-compat endpoint
- `mistral`    — via Mistral API

Config stored at `~/.keel/config.json`. API keys stored there or read from env vars (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `MISTRAL_API_KEY`).

## Key commands
```bash
keel install              # set up all hooks (run once)
keel config               # show current provider/model/keys
keel config provider openrouter
keel config model anthropic/claude-opus-4-6
keel config key openrouter sk-or-...
keel config test          # ping the API
keel process              # process captured queue now
keel weekly               # generate weekly digest
decide resolve <id> -r "reason"  # mark contradiction as deliberate
decide ls / show / diff / patterns
```

## Dev conventions
- **Python 3.9** (macOS system default) — no `X | Y` union syntax, use `Optional[X]`
- Conventional commits: `feat:`, `fix:`, `refactor:`, `chore:`
- All LLM calls go through `llm.complete()` or `llm.stream_complete()` — never import anthropic/openai directly in feature code
- Queue writes must be non-blocking (called on every prompt)
- `~/.keel/` is the data dir — never write to the project directory at runtime

## File layout
```
q/
├── cli.py
├── llm.py          ← unified LLM client
├── config.py       ← provider/model/key config
├── analyzer.py     ← LLM analysis logic
├── processor.py    ← queue processor + classifier
├── digest.py       ← weekly digest generator
├── store.py        ← SQLite decision store
├── queue_writer.py ← hook-called writer (must stay lightweight)
├── install.py      ← hook installer
├── requirements.txt
├── CLAUDE.md
└── .venv/
```

<!-- keel:project:start -->
## Project Decisions (q)
**Real mention detection**: Uses platform-specific adapters for Slack (`@user`) and GitHub (`@user` or team mentions) with format-aware parsing to avoid false positives from basic string matching.

**Autonomous AI execution**: Implements a polling mechanism in `poller.py` to trigger local AI agents when conditions are met, prioritizing simplicity and reliability over event-driven alternatives.

**GitHub/Slack API integration**: Replaces mocks with real API calls in adapters, enabling production-grade interactions while maintaining test coverage for edge cases.

**Style guide enforcement**: Embeds project style rules directly in the shadow agent’s prompt (`shadow_agent.py`) to reduce manual corrections and ensure consistent output.

**Shadow poller expansion**: Follows a structured design spec and implementation plan to address scalability and intelligence gaps in the existing poller.

**Sidebar styling immunity**: Applies 100% inline styles with JavaScript-managed hover/active states to prevent Tailwind CDN timing conflicts from overriding UI behavior.

**Decision documentation**: Captures PR descriptions and review comments in structured JSON, automating context injection to preserve tradeoff discussions for future analysis.

## Cross-Project Principles
**Performance optimization**: Splits large datasets into smaller chunks (e.g., 39k rows) to enable parallel processing and faster dashboard updates without image rebuilds.

**UI consistency**: Relies on inline styles or high-specificity selectors to prevent external stylesheets from disrupting critical interface elements.

**Terminology clarity**: Uses concise, widely understood labels (e.g., "Tech" instead of "Infra") to improve cross-project navigation and reduce cognitive load.
<!-- keel:project:end -->
