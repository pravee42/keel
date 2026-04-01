# keel

> *git diff for your thinking.*

Keel passively watches your AI coding sessions and git commits, extracts the decisions buried inside them, and learns your judgment style over time. When you're about to contradict your past self, it tells you. When enough decisions accumulate, it synthesizes a **developer identity document** — a memory clone of how you think — and injects it into Claude Code and Gemini so every AI session starts with a senior version of you sitting next to it.

---

## How it works

```
Claude Code prompt / git commit / gemini CLI call
  → queue_writer.py   non-blocking hook, appends to ~/.keel/queue.jsonl
  → processor.py      runs every 15 min via LaunchAgent (or: keel process)
      → classify: is this actually a decision?
      → extract: title, context, options, choice, reasoning, principles
      → find similar past decisions
      → consistency diff → macOS notification if contradiction found
      → store in ~/.keel/decisions.db
  → profile.py        runs daily at 7am via LaunchAgent
      → synthesizes full decision history into persona.md
  → inject.py         writes persona into ~/.claude/CLAUDE.md + Gemini
```

---

## Install

```bash
git clone https://github.com/pravee42/keel.git
cd keel
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Add keel to your PATH
echo 'export PATH="$PATH:'"$(pwd)"'"' >> ~/.zshrc && source ~/.zshrc

# Set up hooks + background services
keel install
keel config provider anthropic
keel config key anthropic <your-key>
keel config test
```

That's it. Keel now watches every Claude Code prompt and git commit in the background.

---

## Commands

### Daily use
```bash
keel ls                        # list all tracked decisions
keel show <id>                 # full detail on one decision
keel process                   # process queue manually (normally auto)
keel queue                     # inspect raw captured events
```

### Analysis
```bash
keel patterns                  # your recurring judgment patterns
keel diff <id1> <id2>          # explicit reasoning diff between two decisions
keel correlate                 # decision quality by time-of-day / day-of-week
keel correlate --narrative     # LLM-written mood analysis
keel weekly                    # weekly thinking digest
keel debt                      # tech debt: decisions made under pressure
keel debt --narrative          # prioritized LLM analysis
```

### Pre-commit / pre-PR
```bash
keel check --title "..." --context "..." --reasoning "..."   # check before deciding
keel review                    # review current git diff against your history
keel adr <id>                  # generate Architecture Decision Record
keel adr --auto                # generate ADRs for all arch decisions at once
```

### Memory clone
```bash
keel profile --build           # synthesize developer identity from history
keel profile --show            # print current persona
keel profile --status          # staleness + new decisions since last build
keel inject                    # push persona into Claude Code + Gemini
keel inject --status           # check which tools have persona injected
keel inject --remove           # strip persona from all tools
```

### Background services
```bash
keel service status            # are LaunchAgents running?
keel service install           # register/re-register agents
keel service trigger           # kick off queue processor now
```

### Config
```bash
keel config                    # show current provider / model / keys
keel config provider openrouter
keel config model anthropic/claude-opus-4-6
keel config key openrouter <key>
keel config test               # ping the API
```

---

## Supported LLM providers

| Provider | Flag | Default model |
|---|---|---|
| Anthropic | `anthropic` | claude-opus-4-6 |
| OpenAI | `openai` | gpt-4o |
| OpenRouter | `openrouter` | anthropic/claude-opus-4-6 |
| Gemini | `gemini` | gemini-1.5-pro |
| Mistral | `mistral` | mistral-large-latest |

Anthropic uses adaptive thinking (`thinking: {type: "adaptive"}`) for richer analysis. All others use the OpenAI SDK with `base_url` override.

---

## What gets captured

- **Claude Code prompts** — via `UserPromptSubmit` hook in `~/.claude/settings.json`
- **Git commits** — via global `post-commit` hook (reads commit message + diff stat)
- **Gemini / ChatGPT / Aider / Cursor** — via shell function wrappers in `.zshrc`

Only events that look like real decisions (architectural choices, tradeoffs, tech selections) are stored. Classification runs through your configured LLM — noise is dropped silently.

---

## Data

Everything lives in `~/.keel/`:

```
~/.keel/
├── decisions.db          SQLite — structured decisions
├── queue.jsonl           JSONL — raw captured events (append-only)
├── persona.md            your synthesized developer identity
├── persona_meta.json     build timestamp + decision count
├── config.json           provider / model / API keys
├── digests/              weekly digest JSON files
└── com.keel.*.log        LaunchAgent stdout/stderr logs
```

No data leaves your machine unless you explicitly point keel at a cloud LLM.

---

## Architecture

```
cli.py            Typer CLI entry point
llm.py            unified LLM client (Anthropic native + OpenAI-compat)
config.py         provider/model/key config
store.py          SQLite decisions store
queue_writer.py   hook script — must stay lightweight, called on every prompt
processor.py      queue processor + classifier + consistency checker
analyzer.py       LLM analysis: principles, similarity, consistency diff
digest.py         weekly digest: categorize + narrative
mood.py           time-of-day / day-of-week quality correlation
context.py        personalized system prompt generator
review.py         git diff cross-referenced against decision history
adr.py            Architecture Decision Record generator (Nygard format)
debt.py           tech debt classifier + scorer
profile.py        developer identity synthesizer (memory clone)
inject.py         persona injection into Claude Code / Gemini / OpenAI
service.py        macOS LaunchAgent setup via plistlib
install.py        one-shot hook installer
```

---

## Why "keel"?

A keel is what keeps a ship stable and on course. Keel does the same for your reasoning — it's the thing running underneath everything, making sure you don't drift from your own principles without realizing it.
