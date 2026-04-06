# keel

> *git diff for your thinking. Now with Autonomous Shadow Clone.*

Keel passively watches your AI coding sessions and git commits, extracts the decisions buried inside them, and learns your judgment style over time. When you're about to contradict your past self, it tells you. When enough decisions accumulate, it synthesizes a **developer identity document** — a memory clone of how you think — and injects it into Claude Code, Gemini, and your IDEs so every AI session starts with a senior version of you already loaded in.

**New in v0.2:** Keel now features an **Autonomous Shadow Clone** that can poll Slack, GitHub, and Teams to answer questions and fix code issues on your behalf using your specific persona and technical reasoning.

---

## How it works

```
Claude Code / git commit / gemini CLI / Meeting Transcripts / Slack & GitHub Mentions
  → queue_writer.py     non-blocking hook, appends to ~/.keel/queue.jsonl
  → poller.py           background service, polls Slack/GitHub/Teams for mentions
  → processor.py        runs every 15 min via LaunchAgent (or: keel process)
      → classify: is this actually a decision?
      → extract: title, context, options, choice, reasoning, principles
      → style.py: analyze & replicate developer prompting style
      → meeting.py: extract decisions from verbal discussions
      → consistency diff → macOS notification if contradiction found
      → store in ~/.keel/decisions.db (with strict project isolation)
  → profile.py          synthesizes full decision history into persona.md
  → inject.py           writes global persona into tool configs
  → projects.py         writes context into {repo}/CLAUDE.md + GEMINI.md
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
keel service install
keel config provider anthropic
keel config key anthropic <your-key>
keel config test
```

---

## Commands

### Daily use
```bash
keel ls                        # list all tracked decisions
keel show <id>                 # full detail on one decision
keel process                   # process queue manually (normally auto)
keel queue                     # inspect raw captured events
keel remove <id>               # delete a misclassified decision
keel web                       # start the local web dashboard (Dashboard, Projects, Poller)
```

### Per-project injection
```bash
keel sync                      # sync current repo's CLAUDE.md + GEMINI.md
keel sync --all                # sync all known projects
keel projects                  # list all projects with isolation/archival settings
```

### Memory clone & Intelligence
```bash
keel profile --build           # synthesize developer identity from history
keel inject                    # push persona into Claude Code + Gemini
# Use the Web UI (/intelligence) for Meeting Transcript analysis
# Use the Web UI (/poller) to monitor the Shadow Clone
```

### Analysis & Regret
```bash
keel patterns                  # recurring judgment patterns
keel regret --score            # your Regret Minimization Score + trend
keel quality --stats           # which principles correlate with good outcomes
```

---

## Autonomous Shadow Clone

Keel can act as your "shadow clone" across Slack, GitHub, and Teams. It monitors these platforms for direct mentions of you and automatically responds to questions or fixes code issues using your persona.

*   **High-Certainty Only:** The clone only acts when it is 100% sure it can accurately match your reasoning and tone.
*   **Shadow Identity:** Responds using your own accounts (via user tokens).
*   **On-System Processing:** Only polls and acts when your machine is powered on.

---

## Project Management & Isolation

Every git repository gets its own context block injected into `{repo}/CLAUDE.md` and `{repo}/GEMINI.md`.

*   **Strict Isolation:** Decisions from "Project A" never leak into "Project B" context.
*   **Confidentiality:** Mark projects as `confidential` to prevent their decisions from ever being used as cross-project principles.
*   **Archival:** Archive old projects to stop background syncs while preserving history.

---

## What gets captured

| Source | Mechanism |
|---|---|
| Claude Code prompts | `UserPromptSubmit` hook in `~/.claude/settings.json` |
| Git commits | Global `post-commit` hook (message + diff stat) |
| Gemini CLI | Shell function wrapper (captures input + output) |
| GitHub PRs | `keel github fetch` — PR descriptions + review comments |
| Meetings | Web UI upload — extracts decisions from transcripts/recordings |
| Slack / Teams / GitHub | `poller.py` — captures mentions and thread context |

---

## Data

Everything lives in `~/.keel/`:

```
~/.keel/
├── decisions.db              SQLite — all decisions with project isolation
├── queue.jsonl               JSONL — raw captured events
├── polling_state.json        Last poll timestamps for Slack/GitHub/Teams
├── persona.md                current synthesized developer identity
├── projects/                 per-project metadata (archived, confidential)
└── config.json               provider / model / API keys / platform tokens
```

---

## Architecture

```
cli.py            Typer CLI — all commands
webserver.py      Flask GUI — Dashboard, Projects, Poller, Intelligence
poller.py         Background service for Slack/GitHub/Teams polling
shadow_agent.py   LLM logic for high-certainty persona alignment
style.py          Prompting style learner and guide generator
meeting.py        Meeting transcript decision extractor
processor.py      Queue processor + classifier + consistency checker
analyzer.py       LLM analysis: principles, similarity, isolation logic
llm.py            unified LLM client (Anthropic / OpenAI / Gemini)
store.py          SQLite decisions store
projects.py       Per-project context management and metadata
tool_injector.py  Multi-tool context injection (CLAUDE.md, GEMINI.md, .cursorrules)
install.py        Cross-platform hook and wrapper installer
```

---

## Why "keel"?

A keel is what keeps a ship stable and on course. Keel does the same for your reasoning — it's the thing running underneath everything, making sure you don't drift from your own principles without noticing.
