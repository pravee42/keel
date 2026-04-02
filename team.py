"""Team mode — share decision exports, detect principle conflicts, build a team persona."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import store
import llm

TEAM_DIR = Path.home() / ".keel" / "team"


# ─────────────────────────────────────────────
# Export / Import
# ─────────────────────────────────────────────

def export_decisions(limit: int = 0) -> str:
    """Export own decisions to JSON string for sharing with teammates."""
    decisions = store.get_all()
    if limit:
        decisions = decisions[:limit]
    return json.dumps(
        [
            {
                "id":        d.id,
                "timestamp": d.timestamp,
                "domain":    d.domain,
                "title":     d.title,
                "choice":    d.choice,
                "reasoning": d.reasoning,
                "principles": json.loads(d.principles) if d.principles else [],
                "outcome":   d.outcome,
                "tags":      json.loads(d.tags) if d.tags else [],
            }
            for d in decisions
        ],
        indent=2,
    )


def import_member(name: str, source: str) -> int:
    """Import a teammate's exported decisions JSON. source = file path or JSON string.
    Returns number of decisions imported."""
    TEAM_DIR.mkdir(parents=True, exist_ok=True)
    name = name.lower().replace(" ", "_")

    if Path(source).exists():
        data = json.loads(Path(source).read_text())
    else:
        data = json.loads(source)

    meta = {
        "name":       name,
        "imported_at": datetime.utcnow().isoformat(),
        "count":      len(data),
        "decisions":  data,
    }
    (TEAM_DIR / f"{name}.json").write_text(json.dumps(meta, indent=2))
    return len(data)


def list_members() -> list:
    """Return list of imported team members with metadata."""
    if not TEAM_DIR.exists():
        return []
    members = []
    for f in sorted(TEAM_DIR.glob("*.json")):
        try:
            meta = json.loads(f.read_text())
            members.append({
                "name":        meta["name"],
                "count":       meta["count"],
                "imported_at": meta["imported_at"][:10],
                "file":        f,
            })
        except Exception:
            pass
    return members


def get_member_decisions(name: str) -> list:
    name = name.lower().replace(" ", "_")
    path = TEAM_DIR / f"{name}.json"
    if not path.exists():
        return []
    meta = json.loads(path.read_text())
    return meta.get("decisions", [])


def remove_member(name: str) -> bool:
    name = name.lower().replace(" ", "_")
    path = TEAM_DIR / f"{name}.json"
    if path.exists():
        path.unlink()
        return True
    return False


# ─────────────────────────────────────────────
# Conflict detection
# ─────────────────────────────────────────────

_CONFLICT_PROMPT = """Compare two developers' decision histories and identify principle conflicts.

YOUR PRINCIPLES (extracted from your decisions):
{my_principles}

{member_name}'s PRINCIPLES (extracted from their decisions):
{their_principles}

YOUR RECENT DECISIONS:
{my_decisions}

{member_name}'s RECENT DECISIONS:
{their_decisions}

Identify:
1. Direct conflicts — where you made opposite choices for similar problems
2. Philosophy gaps — where your underlying principles contradict each other
3. Safe overlap — principles you share (briefly)
4. One concrete thing you should discuss to align on

Be specific. Reference actual decisions by title. Keep it under 400 words."""


def find_conflicts(member_name: str) -> Optional[str]:
    """LLM analysis of where your principles conflict with a teammate's."""
    their_decisions = get_member_decisions(member_name)
    if not their_decisions:
        return None

    my_decisions = store.get_all()[:30]

    # Collect principles from both sides
    my_principles: list = []
    for d in my_decisions:
        try:
            my_principles.extend(json.loads(d.principles))
        except Exception:
            pass
    my_principles = list(dict.fromkeys(my_principles))[:20]  # deduplicate, cap

    their_principles: list = []
    for d in their_decisions[:30]:
        their_principles.extend(d.get("principles", []))
    their_principles = list(dict.fromkeys(their_principles))[:20]

    my_lines = "\n".join(
        f"  [{d.timestamp[:10]}] {d.title}: {d.choice[:80]}"
        for d in my_decisions[:15]
    )
    their_lines = "\n".join(
        f"  [{d.get('timestamp', '')[:10]}] {d.get('title', '')}: {d.get('choice', '')[:80]}"
        for d in their_decisions[:15]
    )

    return llm.stream_complete([{"role": "user", "content": _CONFLICT_PROMPT.format(
        my_principles="\n".join(f"  - {p}" for p in my_principles),
        member_name=member_name,
        their_principles="\n".join(f"  - {p}" for p in their_principles),
        my_decisions=my_lines,
        their_decisions=their_lines,
    )}], max_tokens=700)


# ─────────────────────────────────────────────
# Team persona
# ─────────────────────────────────────────────

_TEAM_PERSONA_PROMPT = """Synthesize a shared team engineering philosophy from multiple developers' decision histories.

MEMBERS: {members}

COMBINED DECISIONS (member | title | choice | principles):
{entries}

Write a concise team engineering identity document:
1. **Shared principles** — things everyone agrees on (with evidence)
2. **Ongoing tensions** — areas where the team disagrees or makes inconsistent choices
3. **Emerging patterns** — trends that seem to be forming team-wide
4. **Open questions** — decisions the team hasn't converged on yet

This will be injected into AI coding sessions shared by the team.
Keep it under 600 words. Actionable and specific."""


def build_team_persona() -> Optional[str]:
    """Generate a collective team engineering philosophy from all members' decisions."""
    members = list_members()
    if not members:
        return None

    my_decisions = store.get_all()[:20]
    entries = []

    for d in my_decisions:
        principles = json.loads(d.principles) if d.principles else []
        entries.append(f"me | {d.title} | {d.choice[:60]} | {', '.join(principles[:3])}")

    for m in members:
        for d in m.get("decisions", get_member_decisions(m["name"]))[:15]:
            p_str = ", ".join(d.get("principles", [])[:3])
            entries.append(
                f"{m['name']} | {d.get('title', '')} | "
                f"{d.get('choice', '')[:60]} | {p_str}"
            )

    member_names = ["me"] + [m["name"] for m in members]

    return llm.stream_complete([{"role": "user", "content": _TEAM_PERSONA_PROMPT.format(
        members=", ".join(member_names),
        entries="\n".join(entries[:60]),
    )}], max_tokens=900)
