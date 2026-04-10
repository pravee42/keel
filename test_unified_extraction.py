import processor
import json
import llm

def test_unified_extraction_prompt_structure():
    assert "TRIAGE_EXTRACTION_PROMPT" in dir(processor)
    
    mock_response = json.dumps({
        "is_requirement": True, "requirement_text": "Make it fast", "requirement_type": "Functional", "requirement_priority": "High",
        "is_decision": True, "decision_title": "Use Redis", "decision_context": "Need speed", "decision_options": "Memcached",
        "decision_choice": "Redis", "decision_reasoning": "Faster", "decision_alternatives": ["Memcached"], "is_implicit": False
    })
    
    parsed = processor._parse_json(mock_response, {})
    assert parsed.get("is_requirement") is True
    assert parsed.get("is_decision") is True
    print("Tests passed")

if __name__ == "__main__":
    test_unified_extraction_prompt_structure()
