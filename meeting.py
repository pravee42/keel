"""Extract architectural or strategic decisions from meeting transcripts."""

import json
import llm
from typing import List, Dict

def extract_decisions_from_transcript(transcript_text: str) -> List[Dict]:
    """Extract decisions, context, options, and reasoning from a meeting transcript."""
    if not transcript_text.strip():
        return []

    prompt = f"""You are a senior architect extracting technical and strategic decisions from a meeting transcript.
Your goal is to identify points where a choice was made between multiple options, or a clear direction was set.

For each decision found, extract:
- title: concise one-line summary
- context: the problem or situation being discussed
- options: alternatives considered (if any)
- choice: the final decision reached
- reasoning: why this choice was made

Return ONLY a valid JSON array of objects. If no decisions are found, return [].

TRANSCRIPT:
{transcript_text}

JSON ARRAY:"""

    text = llm.complete([{"role": "user", "content": prompt}], max_tokens=2048).strip()
    
    # Simple JSON extraction logic
    start = text.find("[")
    end = text.rfind("]") + 1
    if start == -1 or end == 0:
        return []
        
    try:
        return json.loads(text[start:end])
    except json.JSONDecodeError:
        return []
