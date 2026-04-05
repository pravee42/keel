"""LLM logic for high-certainty persona alignment and task classification."""

import json
import llm
from typing import Dict

def analyze_mention(message: str, persona_context: str, style_guide: str = "") -> Dict:
    """Analyze a mention using the developer's persona and style guide.
    
    Returns a dict:
    {
      "confidence": int (0-100),
      "action": "reply" | "code" | "ignore",
      "response_text": str,
      "reasoning": str
    }
    """
    if not message.strip() or not persona_context.strip():
        return {"confidence": 0, "action": "ignore", "response_text": "", "reasoning": "Empty input"}

    style_instruction = f"Match this style: {style_guide}" if style_guide else "Match the developer's natural tone."

    prompt = f"""You are a 'Shadow Clone' of a senior developer. 
Your goal is to handle a request addressed to the developer, but ONLY if you are 100% sure you can perfectly match their technical logic and tone.

DEVELOPER PERSONA:
{persona_context}

STYLE GUIDE:
{style_instruction}

REQUEST MESSAGE:
{message}

INSTRUCTIONS:
1. Identify if this is a Question (requires a reply) or a Code Task (requires fixing code).
2. Look through the persona for any past decisions or principles that cover this exact topic.
3. If the persona explicitly covers the logic, set confidence to 100.
4. If the persona is silent or ambiguous, set confidence below 50 and set action to 'ignore'.
5. If action is 'reply', write the response in the developer's exact tone.

Return ONLY a valid JSON object:
{{
  "confidence": 0-100,
  "action": "reply" | "code" | "ignore",
  "response_text": "your proposed reply (if action=reply)",
  "reasoning": "one sentence explaining your confidence level"
}}"""

    text = llm.complete([{"role": "user", "content": prompt}], max_tokens=1024).strip()
    
    # Simple JSON extraction
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        return {"confidence": 0, "action": "ignore", "response_text": "", "reasoning": "Failed to parse JSON"}
        
    try:
        res = json.loads(text[start:end])
        # Ensure default keys
        for key in ["confidence", "action", "response_text", "reasoning"]:
            if key not in res:
                res[key] = "" if key != "confidence" else 0
        return res
    except json.JSONDecodeError:
        return {"confidence": 0, "action": "ignore", "response_text": "", "reasoning": "Invalid JSON"}
