# test_teams_adapter.py
from adapters.teams import TeamsAdapter
from unittest.mock import patch, MagicMock
import json

def test_teams_adapter_send_reply():
    adapter = TeamsAdapter("mock_token")
    with patch('requests.post') as mock_post:
        mock_post.return_value.status_code = 201
        adapter.send_reply("team1/chan1/msg1", "Hello Teams")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs['json']['body']['content'] == "Hello Teams"
        assert "teams/team1/channels/chan1/messages/msg1/replies" in args[0]

if __name__ == "__main__":
    try:
        test_teams_adapter_send_reply()
        print("Test Passed")
    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback
        traceback.print_exc()
