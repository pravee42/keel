# decide — CLAUDE.md

## What this project is
A passive decision-tracking tool that watches your AI CLI prompts and git commits, extracts architectural/strategic decisions, and flags when your reasoning contradicts your past self. "git diff for thinking."

## Architecture
```
queue_writer.py   — lightweight hook script, writes raw events to ~/.decisions/queue.jsonl
processor.py      — classifies events, extracts decisions, runs consistency checks
analyzer.py       — LLM-powered: principle extraction, similarity search, consistency diff
digest.py         — weekly digest: categorizes decisions, generates narrative
config.py         — LLM provider config stored at ~/.decisions/config.json
llm.py            — unified LLM client (Anthropic / OpenAI / OpenRouter / Gemini / Mistral)
store.py          — SQLite store at ~/.decisions/decisions.db
install.py        — sets up Claude Code hooks, git global hooks, shell wrappers, cron
cli.py            — Typer CLI entry point
```

## Data flow
```
Claude Code prompt / git commit / gemini CLI call
  → queue_writer.py  (non-blocking, appends to queue.jsonl)
  → processor.py     (cron every 15 min, or `decide process`)
    → llm.classify()          skip if not a real decision
    → llm.extract_decision()  structured fields
    → analyzer.extract_principles()
    → store.save()
    → analyzer.find_similar() + consistency_diff()
    → macOS notification if inconsistency flagged
  → decide weekly    (Sunday 9am cron, or manual)
```

## Supported LLM providers
- `anthropic` — default, supports adaptive thinking for richer analysis
- `openai`     — via OpenAI API
- `openrouter` — access any model via unified key
- `gemini`     — via Google Generative AI OpenAI-compat endpoint
- `mistral`    — via Mistral API

Config stored at `~/.decisions/config.json`. API keys stored there or read from env vars (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, `MISTRAL_API_KEY`).

## Key commands
```bash
decide install              # set up all hooks (run once)
decide config               # show current provider/model/keys
decide config provider openrouter
decide config model anthropic/claude-opus-4-6
decide config key openrouter sk-or-...
decide config test          # ping the API
decide process              # process captured queue now
decide weekly               # generate weekly digest
decide resolve <id> -r "reason"  # mark contradiction as deliberate
decide ls / show / diff / patterns
```

## Dev conventions
- **Python 3.9** (macOS system default) — no `X | Y` union syntax, use `Optional[X]`
- Conventional commits: `feat:`, `fix:`, `refactor:`, `chore:`
- All LLM calls go through `llm.complete()` or `llm.stream_complete()` — never import anthropic/openai directly in feature code
- Queue writes must be non-blocking (called on every prompt)
- `~/.decisions/` is the data dir — never write to the project directory at runtime

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
