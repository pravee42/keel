# Phase 1 Architecture Diagram

## Event Flow (Multi-Source, Multi-OS, Multi-Tool)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      7 EVENT SOURCES                                     │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  copilot        gemini          cursor          antigravity             │
│  (LSP)          (CLI)           (IDE)           (CLI)                   │
│     │               │               │               │                   │
│     └───────────────┴───────────────┴───────────────┘                   │
│                     ↓                                                    │
│            queue_writer.py (non-blocking)                               │
│            ├─ --source {tool}                                           │
│            ├─ --prompt {user_input}                                     │
│            ├─ --output {llm_response}                                   │
│            └─ Event JSON → ~/.keel/queue.jsonl                          │
│                                                                          │
│  claude-code        git             manual                              │
│  (settings)      (hooks)          (CLI)                                 │
│     │               │               │                                   │
│     └───────────────┴───────────────┘                                   │
└─────────────────────────────────────────────────────────────────────────┘
                             ↓
        ┌─────────────────────────────────────────┐
        │      processor.py (every 15 min)        │
        ├─────────────────────────────────────────┤
        │ 1. Read events from queue               │
        │ 2. Classify: Is this a decision?        │
        │ 3. Extract: _split_prompt_output()      │
        │ 4. Build: Decision dataclass            │
        │ 5. Stamp: source_tool, prompt, output   │
        │ 6. Store: Save to decisions.db          │
        │ 7. Sync: Trigger projects.sync_if_stale│
        └─────────────────────────────────────────┘
                             ↓
        ┌─────────────────────────────────────────┐
        │   store.Decision (SQLite)               │
        ├─────────────────────────────────────────┤
        │ + source_tool (copilot, gemini, ...)   │
        │ + prompt (isolated user input)          │
        │ + output (isolated LLM response)        │
        └─────────────────────────────────────────┘
                             ↓
        ┌─────────────────────────────────────────┐
        │    projects.sync_if_stale()             │
        ├─────────────────────────────────────────┤
        │ Regenerate project context for each    │
        │ project that has new decisions         │
        └─────────────────────────────────────────┘
                             ↓
        ┌─────────────────────────────────────────┐
        │  tool_injector.inject_project_context()│
        ├─────────────────────────────────────────┤
        │ Inject context into:                    │
        │  • .cursorrules (Cursor)                │
        │  • .windsurfrules (Windsurf)            │
        │  • .clinerules (Claude CLI)             │
        │  • .copilot-instructions.md (Copilot)  │
        │  • CLAUDE.md (Claude Code)              │
        └─────────────────────────────────────────┘
                             ↓
        ┌─────────────────────────────────────────┐
        │   AI Tool Context Updated!              │
        ├─────────────────────────────────────────┤
        │ Each tool gets project-specific         │
        │ decision context at next session        │
        └─────────────────────────────────────────┘
```

## Cross-Platform Installation

```
                        keel install
                              │
                ┌─────────────┼─────────────┐
                ↓             ↓             ↓
            macOS           Linux         Windows
          (Darwin)
                │             │             │
        ┌───────┴─────┐   ┌───┴────┐   ┌───┴────┐
        ↓             ↓   ↓        ↓   ↓        ↓
    LaunchAgent   Git  Shell   Cron   Git  Task Sch.
    (service.py)  Hook Wrappers Jobs   Hook
        │          (15min,    │
        │           weekly)   │
        └─────┬──────────────┬┘
              ↓
        Background Processor
        (process queue every 15 min)
```

## Tool Integration Matrix

```
┌──────────────────┬────────────┬─────────────┬──────────────────┐
│ Tool             │ Capture    │ Install     │ Instruction File │
├──────────────────┼────────────┼─────────────┼──────────────────┤
│ Copilot          │ LSP hooks  │ settings.json│ .copilot-...md  │
│ Gemini CLI       │ Shell wrap │ ~/.zshrc    │ N/A (inline)     │
│ Cursor           │ LSP/CLI    │ Shell wrap  │ .cursorrules     │
│ Antigravity      │ Shell wrap │ ~/.zshrc    │ N/A (inline)     │
│ Claude Code      │ settings   │ settings.json│ CLAUDE.md        │
│ Git              │ hook       │ global path │ N/A (commit msg) │
│ Manual (keel)    │ CLI        │ N/A         │ N/A              │
└──────────────────┴────────────┴─────────────┴──────────────────┘
```

## Data Flow: Event → Decision → Context → Tool

```
Input Event (queue_writer.py)
│
├─ source:    "copilot"
├─ prompt:    "Write a function to..."
├─ output:    "def my_func(): ..."
├─ cwd:       "/project/root"
└─ timestamp: "2025-01-30T16:40:00Z"
       │
       ↓ (processor.py _split_prompt_output)
       │
Decision (store.py)
│
├─ id:           "abc123"
├─ title:        "Use async/await for concurrency"
├─ source_tool:  "copilot"
├─ prompt:       "Write a function to..."
├─ output:       "def my_func(): ..."
├─ reasoning:    "Extracted from copilot session"
├─ domain:       "code"
└─ principles:   ["async-first", "performance-optimized"]
       │
       ↓ (projects.sync_if_stale)
       │
Project Context
│
├─ Project Decisions: 3-7 bullets from decisions in THIS project
├─ Active Constraints: 2-4 bullets from decisions tagged "compromise"
└─ Cross-Project Principles: 2-3 bullets from arch decisions
       │
       ↓ (tool_injector.inject_project_context)
       │
Tool-Specific Files
│
├─ .cursorrules              ← Cursor sees project context
├─ .windsurfrules            ← Windsurf sees project context
├─ .clinerules               ← Claude CLI sees project context
├─ .copilot-instructions.md  ← Copilot sees project context
└─ CLAUDE.md                 ← Claude Code sees project context
       │
       ↓ (Tool loads file at session start)
       │
AI Agent Context Ready!
```

## Testing Summary

```bash
Test Name                       Result  Verification
───────────────────────────────────────────────────────
queue_writer: 7 sources         ✓       ~/.keel/queue.jsonl has 7 events
processor: extraction           ✓       Git format splits correctly
platform_utils: paths           ✓       KEEL_HOME resolves correctly
Decision fields                 ✓       source_tool, prompt, output exist
tool_injector: injection        ✓       Module loads, 5 file types supported

Total: 5/5 tests passed
```

## Key Metrics

- **Event Sources**: 7 (copilot, gemini, cursor, antigravity, claude-code, git, manual)
- **Tool-Specific Files**: 5 (.cursorrules, .windsurfrules, .clinerules, .copilot-instructions.md, CLAUDE.md)
- **Operating Systems**: 3 (macOS, Linux, Windows)
- **Event Fields**: 9 (id, timestamp, source, type, cwd, text, prompt, output, processed)
- **Decision Fields Added**: 3 (source_tool, prompt, output)
- **Background Processors**: 3 (LaunchAgent, cron, Task Scheduler)
- **Test Coverage**: 5/5 passing

## Implementation Time

- Phase 1.1 (Event Capture): 30 min
- Phase 1.2 (Processor Enhancement): 25 min
- Phase 1.3 (Cross-Platform Install): 35 min
- **Total**: ~90 minutes (token-efficient)

---

**Status**: Phase 1 Complete ✓

Next: Phase 2 (Advanced capture) or deploy Phase 1 to production
