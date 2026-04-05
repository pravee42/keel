# test_meeting.py
import meeting
from unittest.mock import patch
import json

def test_extract_meeting_decisions():
    transcript = "Alice: Let's use Postgres instead of MySQL because we need JSONB support. Bob: Agreed."
    # We'll mock llm.complete to return JSON
    mock_response = json.dumps([
        {
            "title": "Use Postgres over MySQL",
            "context": "Meeting discussion about database choice.",
            "options": "Postgres, MySQL",
            "choice": "Postgres",
            "reasoning": "Need JSONB support."
        }
    ])
    
    with patch('llm.complete', return_value=mock_response) as mock_llm:
        decisions = meeting.extract_decisions_from_transcript(transcript)
        assert len(decisions) == 1
        assert "Postgres" in decisions[0]["choice"]
        mock_llm.assert_called_once()

if __name__ == "__main__":
    test_extract_meeting_decisions()
    print("Test Passed")
