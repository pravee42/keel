"""Generate a personalized system prompt from decision history.

Two modes:
  global  — full principle profile, injectable into any AI session
  path    — decisions touching a specific file/module, for re-onboarding
"""

import json
from pathlib import Path
from typing import Optional

import llm
import store

SYSTEM_PROMPT_PATH = Path.home() / ".keel" / "system_prompt.md"

# ─────────────────────────────────────────────
# Global context (AI session injection)
# ─────────────────────────────────────────────

PROFILE_PROMPT = """Based on this person's decision history, write a concise personal system prompt
they can inject into any AI coding session. The AI should behave like a senior collaborator
who already knows this person's preferences and past choices.

Format as markdown. Include:
1. **Architecture preferences** — patterns, structures, tools they consistently choose
2. **Things they avoid** — explicitly rejected approaches with reasons
3. **Active tradeoffs** — known compromises still in place (from 'compromise'/'temporary' tagged decisions)
4. **Reasoning style** — how they approach decisions (fast/methodical, principle-driven/pragmatic, etc.)

Keep it under 400 words. Use bullet points. Write in second person ("You prefer...").
This will be prepended to every AI prompt, so be dense and specific.

DECISION HISTORY:
{history}

EXTRACTED PRINCIPLES (aggregated):
{principles}"""


def generate_system_prompt(decisions: list[store.Decision]) -> str:
    if not decisions:
        return "# No decision history yet.\n\nLog some decisions with `decide log` to build your profile."

    history = "\n\n".join(
        f"[{d.domain}] {d.title}\n"
        f"Choice: {d.choice}\n"
        f"Reasoning: {d.reasoning[:300]}\n"
        f"Tags: {', '.join(json.loads(d.tags)) or 'none'}"
        for d in decisions[:60]
    )

    all_principles = []
    for d in decisions:
        all_principles.extend(json.loads(d.principles))
    from collections import Counter
    top = [p for p, _ in Counter(all_principles).most_common(20)]

    result = llm.stream_complete(
        [{"role": "user", "content": PROFILE_PROMPT.format(
            history=history,
            principles="\n".join(f"- {p}" for p in top),
        )}],
        max_tokens=1024,
    )
    return result


def save_system_prompt(content: str) -> Path:
    SYSTEM_PROMPT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SYSTEM_PROMPT_PATH.write_text(content)
    return SYSTEM_PROMPT_PATH


def inject_into_claude_code(content: str, project_path: Optional[Path] = None) -> Path:
    """Write/update the system prompt into a CLAUDE.md file."""
    target = (project_path / "CLAUDE.md") if project_path else (Path.home() / ".claude" / "CLAUDE.md")
    target.parent.mkdir(parents=True, exist_ok=True)

    marker_start = "<!-- decide:profile:start -->"
    marker_end   = "<!-- decide:profile:end -->"
    block = f"{marker_start}\n## My Development Profile\n\n{content}\n{marker_end}"

    existing = target.read_text() if target.exists() else ""

    if marker_start in existing:
        # Replace existing block
        import re
        updated = re.sub(
            rf"{re.escape(marker_start)}.*?{re.escape(marker_end)}",
            block,
            existing,
            flags=re.DOTALL,
        )
    else:
        updated = existing.rstrip() + f"\n\n{block}\n"

    target.write_text(updated)
    return target


# ─────────────────────────────────────────────
# Path/module context (re-onboarding)
# ─────────────────────────────────────────────

PATH_CONTEXT_PROMPT = """Summarize all decisions that affected this module/path, in chronological order.
Write like a knowledgeable colleague briefing someone returning from vacation.

Module/path: {path}

RELEVANT DECISIONS:
{decisions_text}

Include:
- What was decided and when
- The reasoning behind each decision
- Any known tradeoffs or tech debt
- What to watch out for when touching this code

Max 300 words. Be specific."""


def module_context(path_fragment: str, decisions: Optional[list[store.Decision]] = None) -> str:
    if decisions is None:
        decisions = store.get_all()

    # Find decisions that mention this path or have matching domain keywords
    relevant = [d for d in decisions if path_fragment.lower() in (
        d.paths + " " + d.context + " " + d.choice + " " + d.reasoning
    ).lower()]

    if not relevant:
        return f"No decisions found touching `{path_fragment}`.\n\nThis path hasn't been explicitly reasoned about yet."

    decisions_text = "\n\n".join(
        f"[{d.timestamp[:10]}] {d.title}\n"
        f"Choice: {d.choice}\n"
        f"Reasoning: {d.reasoning}\n"
        f"Tags: {', '.join(json.loads(d.tags)) or 'none'}\n"
        f"Outcome: {d.outcome or 'not recorded'}"
        for d in sorted(relevant, key=lambda x: x.timestamp)
    )

    return llm.stream_complete(
        [{"role": "user", "content": PATH_CONTEXT_PROMPT.format(
            path=path_fragment,
            decisions_text=decisions_text,
        )}],
        max_tokens=1024,
    )
