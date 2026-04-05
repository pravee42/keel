# test_poller_scaffold.py
import poller
from unittest.mock import patch, MagicMock
import json

def test_poller_loop_logic():
    # Mocking adapters and shadow agent to test the loop logic
    mock_slack = MagicMock()
    mock_slack.source = "slack"
    mock_slack.get_mentions.return_value = [{"id": "s1", "text": "Fix this", "source": "slack"}]
    
    mock_agent = MagicMock()
    mock_agent.analyze_mention.return_value = {"confidence": 100, "action": "reply", "response_text": "Fixed"}
    
    with patch('poller.SlackAdapter', return_value=mock_slack):
        with patch('shadow_agent.analyze_mention', return_value=mock_agent.analyze_mention.return_value):
            # We don't want to actually run the loop forever, so we mock time.sleep to raise an exception
            with patch('time.sleep', side_effect=InterruptedError):
                try:
                    # Mocking config, state, and persona
                    with patch('config.load', return_value={"api_keys": {"slack": "tok"}}):
                        with patch('poller.load_state', return_value={"last_poll_at": "2026-01-01T00:00:00Z", "processed_ids": []}):
                            with patch('profile.load_persona', return_value="Persona"):
                                poller.run_poller_once()
                                # Verify slack mentions were fetched
                                mock_slack.get_mentions.assert_called()
                                # Verify slack reply was sent
                                mock_slack.send_reply.assert_called_once_with("s1", "Fixed")
                except InterruptedError:
                    pass

if __name__ == "__main__":
    # This test will fail until adapters are created
    try:
        test_poller_loop_logic()
        print("Test Passed")
    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback
        traceback.print_exc()
