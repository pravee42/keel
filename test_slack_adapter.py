# test_slack_adapter.py
from adapters.slack import SlackAdapter
from unittest.mock import patch, MagicMock
import json

def test_slack_adapter_send_reply():
    adapter = SlackAdapter("mock_token")
    with patch('requests.post') as mock_post:
        mock_post.return_value.status_code = 200
        adapter.send_reply("C123/12345.000", "Hello")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs['json']['text'] == "Hello"
        assert kwargs['json']['channel'] == "C123"
        assert kwargs['json']['thread_ts'] == "12345.000"

if __name__ == "__main__":
    try:
        test_slack_adapter_send_reply()
        print("Test Passed")
    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback
        traceback.print_exc()
