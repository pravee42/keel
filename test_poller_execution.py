# test_poller_execution.py
from unittest.mock import patch, MagicMock
import poller
import os
import json

def test_code_execution_trigger():
    # Setup mock mention with repo_path
    mock_mention = {
        "id": "gh1",
        "source": "github",
        "text": "Fix the bug in main.py",
        "repo_path": "/tmp/test_repo"
    }
    
    # Mock OS path exists
    with patch('os.path.exists', return_value=True):
        # Mock shadow_agent.analyze_mention to return code action
        with patch('shadow_agent.analyze_mention', return_value={"confidence": 100, "action": "code"}):
            # Mock subprocess.Popen
            with patch('subprocess.Popen') as mock_popen:
                # Mock other dependencies to isolate execution logic
                with patch('config.load', return_value={"api_keys": {"github": "tok"}}):
                    with patch('poller.load_state', return_value={"last_poll_at": "...", "processed_ids": []}):
                        with patch('profile.load_persona', return_value="Persona"):
                            with patch('style.analyze_prompting_style', return_value="Style"):
                                # Mock GitHubAdapter
                                mock_adapter = MagicMock()
                                mock_adapter.source = "github"
                                mock_adapter.get_mentions.return_value = [mock_mention]
                                
                                with patch('poller.GitHubAdapter', return_value=mock_adapter):
                                    poller.run_poller_once()
                                    
                                    # Verify subprocess.Popen was called with gemini or similar
                                    mock_popen.assert_called()
                                    args, kwargs = mock_popen.call_args
                                    assert "gemini" in args[0] or "claude" in args[0]
                                    assert kwargs['cwd'] == "/tmp/test_repo"
                                    
                                    # Verify acknowledgment reply
                                    mock_adapter.send_reply.assert_called_once()

if __name__ == "__main__":
    try:
        test_code_execution_trigger()
        print("Test Passed")
    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback
        traceback.print_exc()
