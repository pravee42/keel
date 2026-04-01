"""Auto-generate Architecture Decision Records from captured decisions."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

import llm
import store

ADR_DIR = Path("docs/decisions")   # relative to cwd — project-local

ADR_PROMPT = """Generate a formal Architecture Decision Record (ADR) for this decision.
Follow the Michael Nygard format exactly.

DECISION DATA:
Title: {title}
Date: {date}
Domain: {domain}
Context: {context}
Options considered: {options}
Choice made: {choice}
Reasoning: {reasoning}
Principles applied: {principles}
Tags: {tags}
Outcome (if known): {outcome}

Output ONLY the markdown content, no preamble:

# ADR-{number}: {title}

Date: {date}
Status: Accepted

## Context
<2-3 sentences about the situation that required a decision>

## Decision
<one clear sentence stating what was decided>

## Options Considered
<bullet list of alternatives that were weighed>

## Reasoning
<the why — extracted from the decision data, written in complete sentences>

## Consequences
### Positive
<bullet list>
### Negative / Tradeoffs
<bullet list — include any 'compromise' or 'temporary' tagged concerns>

## Related Decisions
<list any IDs from the history if relevant, else "None">"""


def _next_adr_number(adr_dir: Path) -> int:
    if not adr_dir.exists():
        return 1
    existing = list(adr_dir.glob("ADR-*.md"))
    if not existing:
        return 1
    numbers = []
    for f in existing:
        m = re.match(r"ADR-(\d+)", f.stem)
        if m:
            numbers.append(int(m.group(1)))
    return max(numbers) + 1 if numbers else 1


def generate_adr(d: store.Decision, adr_dir: Optional[Path] = None) -> tuple[str, Path]:
    """Generate ADR content and return (content, file_path)."""
    target_dir = adr_dir or ADR_DIR
    number = _next_adr_number(target_dir)

    principles = ", ".join(json.loads(d.principles)) or "none extracted"
    tags       = ", ".join(json.loads(d.tags)) or "none"
    date       = d.timestamp[:10]

    content = llm.stream_complete(
        [{"role": "user", "content": ADR_PROMPT.format(
            number=str(number).zfill(3),
            title=d.title,
            date=date,
            domain=d.domain,
            context=d.context,
            options=d.options,
            choice=d.choice,
            reasoning=d.reasoning,
            principles=principles,
            tags=tags,
            outcome=d.outcome or "not yet recorded",
        )}],
        max_tokens=1024,
    )

    # Sanitize title for filename
    slug = re.sub(r"[^\w\s-]", "", d.title.lower())
    slug = re.sub(r"[\s]+", "-", slug.strip())[:50]
    filename = target_dir / f"ADR-{str(number).zfill(3)}-{slug}.md"

    target_dir.mkdir(parents=True, exist_ok=True)
    filename.write_text(content)
    return content, filename


def should_generate_adr(d: store.Decision) -> bool:
    """Heuristic: generate ADR for architectural decisions."""
    tags = json.loads(d.tags)
    return d.domain == "code" and (
        "arch" in tags or
        any(w in (d.title + d.choice + d.reasoning).lower() for w in [
            "chose", "use", "adopt", "migrate", "replace", "switch",
            "architecture", "pattern", "framework", "database", "auth",
        ])
    )


def list_adrs(adr_dir: Optional[Path] = None) -> list[dict]:
    target_dir = adr_dir or ADR_DIR
    if not target_dir.exists():
        return []
    adrs = []
    for f in sorted(target_dir.glob("ADR-*.md")):
        content = f.read_text()
        # Extract title from first H1
        title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
        date_match  = re.search(r"^Date: (.+)$", content, re.MULTILINE)
        status_match = re.search(r"^Status: (.+)$", content, re.MULTILINE)
        adrs.append({
            "file":   f.name,
            "title":  title_match.group(1) if title_match else f.stem,
            "date":   date_match.group(1) if date_match else "unknown",
            "status": status_match.group(1) if status_match else "unknown",
        })
    return adrs
