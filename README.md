# keel

> *git diff for your thinking.*

Keel passively watches your AI coding sessions and git commits, extracts the decisions buried inside them, and learns your judgment style over time. When you're about to contradict your past self, it tells you. When enough decisions accumulate, it synthesizes a **developer identity document** — a memory clone of how you think — and injects it into Claude Code and Gemini so every AI session starts with a senior version of you already loaded in.

Each project gets its own context block, auto-maintained. You never have to touch it.

---

## How it works

```
Claude Code prompt / git commit / gemini CLI call / any OpenAI-compat tool / GitHub PR
  → queue_writer.py     non-blocking hook, appends to ~/.keel/queue.jsonl
  → processor.py        runs every 15 min via LaunchAgent (or: keel process)
      → classify: is this actually a decision?
      → extract: title, context, options, choice, reasoning, principles
      → detect git root → stamp decision with project path
      → find similar past decisions
      → consistency diff → macOS notification if contradiction found
      → store in ~/.keel/decisions.db
      → sync project CLAUDE.md if new decisions since last sync
  → profile.py          runs daily at 7am via LaunchAgent
      → synthesizes full decision history into persona.md
      → snapshots versioned copy to ~/.keel/personas/
  → inject.py           writes global persona into ~/.claude/CLAUDE.md + Gemini
  → projects.py         writes per-project context into {repo}/CLAUDE.md
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

That's it. Keel now watches every Claude Code prompt and git commit in the background, and keeps every project's `CLAUDE.md` up to date automatically.

---

## Commands

### Daily use
```bash
keel ls                        # list all tracked decisions
keel show <id>                 # full detail on one decision
keel process                   # process queue manually (normally auto)
keel queue                     # inspect raw captured events
keel remove <id>               # delete a misclassified decision
keel correct <id>              # interactively fix a poorly extracted decision
```

### Per-project injection
```bash
keel sync                      # sync current git repo's CLAUDE.md
keel sync --all                # sync all known projects
keel sync --force              # regenerate even if not stale
keel projects                  # list all projects with decision counts + sync status
keel projects --sync           # list and sync all
keel projects --remove <path>  # strip keel block from a project's CLAUDE.md
```

### Memory clone (global persona)
```bash
keel profile --build           # synthesize developer identity from all history
keel profile --show            # print current persona
keel profile --status          # staleness + decisions since last build
keel profile --versions        # list dated persona snapshots
keel profile --diff            # LLM analysis: how your thinking changed
keel profile --from 2025-11 --to 2026-01  # diff specific versions
keel inject                    # push persona into Claude Code + Gemini + OpenAI
keel inject --status           # which tools have persona injected
keel inject --remove           # strip persona from all tools
```

### Analysis
```bash
keel patterns                  # recurring judgment patterns
keel diff <id1> <id2>          # reasoning diff between two decisions
keel correlate                 # decision quality by time-of-day / day-of-week
keel correlate --narrative     # LLM-written mood analysis
keel weekly                    # weekly thinking digest
keel debt                      # tech debt: decisions made under pressure
keel debt --narrative          # prioritized LLM analysis
```

### Regret minimization
```bash
keel regret --pending          # decisions flagged as contradictions, awaiting classification
keel regret --growth <id> --note "learned X"     # mark as deliberate reversal
keel regret --regret <id> --note "forgot past reasoning"  # mark as accidental drift
keel regret --score            # your Regret Minimization Score + trend
keel regret --list             # all classified decisions
keel regret --narrative        # LLM analysis of your change-of-mind pattern
```

### Outcome quality
```bash
keel outcome <id> --text "shipped to prod, zero issues"    # record what happened
keel quality <id> --rating good        # rate: good | neutral | bad
keel quality --stats                   # which principles correlate with good outcomes
keel quality --narrative               # LLM: which principles to trust / stop using
```

### GitHub PR capture
```bash
keel github config --token ghp_...    # store your GitHub token (one-time setup)
keel github detect                    # show auto-detected repo from git remote
keel github fetch                     # fetch PRs from current repo (last 30 days)
keel github fetch --repo owner/repo   # specific repo
keel github fetch --since 60          # look back further
keel github fetch --pr 42             # single PR
keel github fetch --process           # fetch + process immediately
```

### Token cost tracking
```bash
keel cost                      # last 30 days: total spend + per-model breakdown
keel cost --since 7            # last 7 days
keel cost --breakdown          # daily spend bar chart
keel cost --reset              # clear usage log
```

### Team mode
```bash
keel team export --output mine.json    # export your decisions to share
keel team add --name alice --file alice.json   # import a teammate's history
keel team list                         # list imported team members
keel team conflicts --name alice       # LLM: where your principles clash
keel team persona                      # build shared team engineering philosophy
keel team remove --name alice          # remove a member's data
```

### Pre-commit / pre-PR
```bash
keel check --title "..." --context "..." --reasoning "..."
keel review                    # review current git diff against your history
keel adr <id>                  # generate Architecture Decision Record
keel adr --auto                # generate ADRs for all arch decisions at once
```

### Local proxy (replaces shell wrappers)
```bash
keel proxy start               # start logging proxy on localhost:4422
keel proxy install             # install as always-on LaunchAgent
keel proxy status              # is it running?
keel proxy stop

# Point any OpenAI-compatible tool at it:
export OPENAI_BASE_URL=http://localhost:4422/v1
aider --openai-api-base http://localhost:4422/v1
```

### Background services
```bash
keel service install           # register all LaunchAgents
keel service status            # running / stopped per agent
keel service trigger           # kick off collector now
keel service uninstall         # remove all agents
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

## Per-project injection

Every git repository you work in gets its own compact context block injected into `{repo}/CLAUDE.md`. Claude Code reads it at session start.

**What lands in each project:**

```markdown
<!-- keel:project:start -->
<!-- auto-generated by keel · 2026-04-01 08:30 UTC · do not edit this block -->
## Project Decisions (myapp)

- **SQLite over Postgres**: zero-dependency deployment; acceptable until multi-user scale
- **No ORM**: direct sqlite3; rejected in 4 projects — abstraction cost exceeds benefit

## Active Constraints

- JWT auth is a temporary compromise — session store deferred (tagged 2024-03)

## Cross-Project Principles

- Explicit over implicit in all dependency wiring (consistent across 6 projects)
<!-- keel:project:end -->
```

Content is kept to ~500–800 tokens. Re-injected automatically after each decision is saved for that project. The block uses distinct markers from the global persona so both can coexist in the same file.

---

## Regret Minimization Score

For every contradiction keel flags, you classify it:
- **Growth** — deliberate reversal, you learned something, context changed
- **Regret** — accidental drift, you forgot past reasoning

Over time this builds a score (0–100%) showing how often you change your mind on purpose vs. by accident. High score = you're learning. Low score = you're drifting.

```bash
keel regret --pending   # interactive review with AI suggestions
keel regret --score     # your score, trend, breakdown by domain
```

---

## Outcome quality correlation

Once you record outcomes on past decisions, keel builds a table showing which of your principles actually produce good results.

```bash
keel outcome <id> --text "worked well in production"
keel quality <id> --rating good
keel quality --stats        # principle → good/neutral/bad outcome table
keel quality --narrative    # LLM: which principles to double down on, which to question
```

---

## GitHub PR capture

PR descriptions and review comments are where your most explicit tradeoff reasoning lives. Keel can pull them in:

```bash
keel github config --token ghp_...      # one-time setup
keel github fetch --process             # pull PRs + extract decisions immediately
```

Decisions extracted from PRs go through the same pipeline as everything else — consistency check, principle extraction, persona injection.

---

## Token cost visibility

Every keel LLM call logs token counts and estimated cost to `~/.keel/usage.jsonl`.

```bash
keel cost               # total spend + per-model breakdown
keel cost --breakdown   # daily chart
```

---

## Team mode

Share decision histories with teammates and find where your engineering principles diverge.

```bash
keel team export --output mine.json     # share with a teammate
keel team add --name alice --file alice.json
keel team conflicts --name alice        # where do you disagree?
keel team persona                       # shared team philosophy
```

---

## What gets captured

| Source | Mechanism |
|---|---|
| Claude Code prompts | `UserPromptSubmit` hook in `~/.claude/settings.json` |
| Git commits | Global `post-commit` hook (message + diff stat) |
| GitHub PRs | `keel github fetch` — PR descriptions + review comments |
| Gemini / ChatGPT / Aider / Cursor | Shell wrappers in `.zshrc` (fallback) |
| Any OpenAI-compat tool | Local proxy on `localhost:4422` (preferred) |

Only events that look like real decisions are stored. The classifier runs every event through your configured LLM — noise is dropped silently.

---

## Background services

Three LaunchAgents run automatically after `keel service install`:

| Agent | Schedule | What it does |
|---|---|---|
| `com.keel.collector` | Every 15 min | Process queue, extract decisions, sync stale projects |
| `com.keel.profile` | Daily at 7am | Rebuild persona, snapshot versioned copy, inject globally |
| `com.keel.sync` | Every 6 hours | Sync all project CLAUDE.md files (backstop for cross-project changes) |

---

## Data

Everything lives in `~/.keel/`:

```
~/.keel/
├── decisions.db              SQLite — all decisions with project, paths, tags, outcome quality
├── queue.jsonl               JSONL — raw captured events (append-only)
├── usage.jsonl               JSONL — LLM token usage + cost per call
├── diffs/                    consistency diff sidecars per decision
├── persona.md                current synthesized developer identity
├── persona_meta.json         build timestamp + decision count
├── personas/                 dated snapshots: persona_YYYY-MM-DD.md
├── projects/                 per-project sync metadata JSON files
├── team/                     imported teammate decision exports
├── config.json               provider / model / API keys / github token
├── digests/                  weekly digest JSON files
├── proxy.pid                 proxy server PID (when running)
└── com.keel.*.log            LaunchAgent stdout/stderr logs
```

No data leaves your machine unless you explicitly point keel at a cloud LLM.

---

## Architecture

```
cli.py            Typer CLI — all commands
llm.py            unified LLM client (Anthropic native + OpenAI-compat) + usage logging
config.py         provider / model / key config
store.py          SQLite decisions store (with project, outcome quality tracking)
queue_writer.py   hook script — lightweight, called on every prompt
processor.py      queue processor + classifier + consistency checker
analyzer.py       LLM analysis: principles, similarity, consistency diff
digest.py         weekly digest: categorize + narrative
mood.py           time-of-day / day-of-week quality correlation
context.py        personalized system prompt generator
review.py         git diff cross-referenced against decision history
adr.py            Architecture Decision Record generator (Nygard format)
debt.py           tech debt classifier + scorer
regret.py         Regret Minimization Score — deliberate vs accidental change
quality.py        outcome quality correlation — which principles produce good results
github.py         GitHub PR capture — fetch PR descriptions + review comments
cost.py           token usage tracking + cost estimation per model
team.py           team mode — export/import decisions, conflict detection, team persona
profile.py        developer identity synthesizer + versioned snapshots
inject.py         global persona injection (Claude Code / Gemini / OpenAI)
projects.py       per-project context injection into repo CLAUDE.md files
proxy.py          local OpenAI-compatible logging proxy (stdlib only)
service.py        macOS LaunchAgent setup via plistlib
install.py        one-shot hook installer
```

---

## Why "keel"?

A keel is what keeps a ship stable and on course. Keel does the same for your reasoning — it's the thing running underneath everything, making sure you don't drift from your own principles without noticing.
