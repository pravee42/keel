"""Pre-PR code review ghost — scan a git diff against decision history."""

import json
import subprocess
from typing import Optional

import llm
import store

REVIEW_PROMPT = """You are a code review assistant who knows this developer's full decision history.
Review the diff below and flag any lines that contradict or drift from their past decisions.

DEVELOPER'S DECISION HISTORY:
{history}

PRINCIPLES THEY FOLLOW:
{principles}

GIT DIFF:
```diff
{diff}
```

For each issue found, output:
FILE: <filename>
LINE: <line number or range>
SEVERITY: drift | contradiction | tech-debt | consistent
DECISION: [<id>] <decision title it relates to>
NOTE: <one sentence — what conflicts and why it matters>

Then a SUMMARY section:
SUMMARY:
- N issues found (X contradictions, Y drifts, Z consistent confirmations)
- <one key observation>

If nothing conflicts, say: "LGTM — no conflicts with your decision history."
Be specific, cite line numbers. Skip cosmetic issues."""


def get_git_diff(base: str = "HEAD", path: Optional[str] = None) -> str:
    cmd = ["git", "diff", base]
    if path:
        cmd.append(path)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Try staged diff
        result = subprocess.run(["git", "diff", "--cached"], capture_output=True, text=True)
    return result.stdout


def review_diff(diff_text: str, decisions: Optional[list[store.Decision]] = None) -> str:
    if not diff_text.strip():
        return "No diff found. Stage your changes or pass a diff via --diff."

    if decisions is None:
        decisions = store.get_all()

    if not decisions:
        return "No decision history yet. Can't review without context."

    history = "\n\n".join(
        f"[{d.id}] {d.title} ({d.timestamp[:10]})\n"
        f"Domain: {d.domain} | Tags: {', '.join(json.loads(d.tags)) or 'none'}\n"
        f"Choice: {d.choice}\n"
        f"Reasoning: {d.reasoning[:300]}"
        for d in decisions[:40]
    )

    all_principles: list = []
    for d in decisions:
        all_principles.extend(json.loads(d.principles))
    from collections import Counter
    top_principles = "\n".join(
        f"- {p}" for p, _ in Counter(all_principles).most_common(15)
    )

    return llm.stream_complete(
        [{"role": "user", "content": REVIEW_PROMPT.format(
            history=history,
            principles=top_principles,
            diff=diff_text[:6000],  # cap to avoid token overflow
        )}],
        max_tokens=2048,
    )
