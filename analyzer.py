"""Claude-powered analysis: principle extraction, similarity, consistency diff."""

import json
import llm
from store import Decision


def extract_principles(d: Decision) -> list[str]:
    prompt = f"""Analyze this decision and extract 2-5 implicit principles or heuristics the person used.
Return ONLY a JSON array of short principle strings (under 15 words each).

Decision: {d.title}
Domain: {d.domain}
Context: {d.context}
Options considered: {d.options}
Choice made: {d.choice}
Reasoning: {d.reasoning}

Return only valid JSON like: ["principle one", "principle two"]"""

    text = llm.complete([{"role": "user", "content": prompt}], max_tokens=512).strip()
    start, end = text.find("["), text.rfind("]") + 1
    if start == -1 or end == 0:
        return []
    return json.loads(text[start:end])


def find_similar(new_decision: Decision, history: list[Decision], top_n: int = 3) -> list[tuple[Decision, str]]:
    if not history:
        return []

    history_text = "\n\n".join(
        f"[{d.id}] {d.title} ({d.domain})\nContext: {d.context[:200]}\nChoice: {d.choice}\nReasoning: {d.reasoning[:300]}"
        for d in history[:30]
    )

    prompt = f"""Given this new decision, identify the {top_n} most similar past decisions from the history below.
"Similar" means: same type of tradeoff, same domain tensions, or structurally analogous situation.

NEW DECISION:
Title: {new_decision.title}
Domain: {new_decision.domain}
Context: {new_decision.context}
Reasoning: {new_decision.reasoning}

PAST DECISIONS:
{history_text}

Return ONLY a JSON array:
[{{"id": "abc123", "reason": "both involve choosing speed over correctness under deadline pressure"}}]
Return [] if nothing is similar."""

    text = llm.complete([{"role": "user", "content": prompt}], max_tokens=1024).strip()
    start, end = text.find("["), text.rfind("]") + 1
    if start == -1 or end == 0:
        return []

    matches = json.loads(text[start:end])
    id_map = {d.id: d for d in history}
    return [(id_map[m["id"]], m["reason"]) for m in matches if m["id"] in id_map]


def consistency_diff(new_decision: Decision, similar: list[tuple[Decision, str]]) -> str:
    if not similar:
        return "No similar past decisions to compare against."

    comparisons = "\n\n".join(
        f"Past decision [{d.id}] — {d.title}\n"
        f"Similarity: {reason}\n"
        f"Context: {d.context}\n"
        f"Choice: {d.choice}\n"
        f"Reasoning: {d.reasoning}\n"
        f"Principles used: {d.principles}"
        for d, reason in similar
    )

    prompt = f"""You are analyzing whether a person's reasoning is consistent with their past decisions.
Do NOT judge whether the decisions are good or bad — only whether the reasoning is consistent.

NEW DECISION:
Title: {new_decision.title}
Context: {new_decision.context}
Choice: {new_decision.choice}
Reasoning: {new_decision.reasoning}

SIMILAR PAST DECISIONS:
{comparisons}

Analyze:
1. What principles/heuristics guided the past decisions?
2. Does the new decision follow the same principles?
3. If inconsistent: what specifically changed, and is it a legitimate context-driven shift or unexplained contradiction?

Be specific. Quote the reasoning. Keep it under 300 words."""

    return llm.stream_complete([{"role": "user", "content": prompt}], max_tokens=1024)


def summarize_patterns(decisions: list[Decision]) -> str:
    if not decisions:
        return "No decisions logged yet."

    history_text = "\n\n".join(
        f"[{d.domain}] {d.title}\nChoice: {d.choice}\nReasoning: {d.reasoning[:400]}\nPrinciples: {d.principles}"
        for d in decisions[:50]
    )

    prompt = f"""Analyze this person's decision history and identify their judgment style.

DECISIONS:
{history_text}

Extract:
1. Recurring principles (what do they consistently optimize for?)
2. Domain-specific patterns (do they reason differently in code vs. life vs. business?)
3. Known blind spots or tensions in their reasoning
4. How their thinking has evolved over time (if visible)

Be specific and cite examples. This is a mirror, not advice."""

    return llm.stream_complete([{"role": "user", "content": prompt}], max_tokens=2048)
