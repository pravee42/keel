# test_style.py
import style
from store import Decision
import json
from unittest.mock import patch

def test_analyze_style():
    decisions = [
        Decision(id="1", timestamp="", domain="code", title="", context="", options="", choice="", 
                 reasoning="Keep it simple. One file, one job.", principles="[]", outcome="", 
                 tags="[]", paths="[]", project="")
    ]
    # We'll mock llm.complete since we don't have real keys
    with patch('llm.complete', return_value="This developer is concise and prefers simple architectures.") as mock_llm:
        style_profile = style.analyze_prompting_style(decisions)
        assert "concise" in style_profile.lower() or "simple" in style_profile.lower()
        mock_llm.assert_called_once()

if __name__ == "__main__":
    test_analyze_style()
    print("Test Passed")
