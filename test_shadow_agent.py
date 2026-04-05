# test_shadow_agent.py
import shadow_agent
from unittest.mock import patch
import json

def test_high_certainty_filter_reply():
    message = "How do we handle auth in this project?"
    persona = "The developer always prefers JWT for internal services and OAuth2 for public ones."
    style_guide = "Concise and direct."
    
    mock_response = json.dumps({
        "confidence": 100,
        "action": "reply",
        "response_text": "We use JWT for internal services and OAuth2 for public ones."
    })
    
    with patch('llm.complete', return_value=mock_response) as mock_llm:
        response = shadow_agent.analyze_mention(message, persona, style_guide)
        assert response["confidence"] == 100
        assert response["action"] == "reply"
        assert "JWT" in response["response_text"]
        mock_llm.assert_called_once()

def test_low_confidence_ignore():
    message = "What's the meaning of life?"
    persona = "The developer knows about Python and React."
    
    mock_response = json.dumps({
        "confidence": 10,
        "action": "ignore",
        "response_text": ""
    })
    
    with patch('llm.complete', return_value=mock_response) as mock_llm:
        response = shadow_agent.analyze_mention(message, persona)
        assert response["confidence"] < 50
        assert response["action"] == "ignore"

if __name__ == "__main__":
    try:
        test_high_certainty_filter_reply()
        test_low_confidence_ignore()
        print("Test Passed")
    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback
        traceback.print_exc()
