"""Analyze the developer's prompting and reasoning style."""

import llm
from store import Decision
from typing import List

def analyze_prompting_style(decisions: List[Decision]) -> str:
    """Analyze the developer's written reasoning to extract stylistic traits."""
    if not decisions:
        return "Standard professional tone."
    
    # Take latest 20 decisions to analyze style
    samples = "\n".join([f"- {d.reasoning}" for d in decisions[:20] if d.reasoning])
    
    if not samples:
        return "Standard professional tone."

    prompt = f"""You are a professional linguist and developer coach.
Analyze the following text samples written by a developer (their 'reasoning' for decisions).
Identify:
1. Verbosity (Are they concise or verbose?)
2. Technical Depth (Do they prefer high-level abstractions or low-level details?)
3. Tone (Are they direct, cautious, optimistic, or cynical?)
4. Specific jargon or formatting preferences.

Return a concise 2-3 sentence 'Style Guide' for this developer.

REASONING SAMPLES:
{samples}

STYLE GUIDE:"""

    return llm.complete([{"role": "user", "content": prompt}], max_tokens=256).strip()
