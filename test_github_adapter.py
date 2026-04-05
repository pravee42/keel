# test_github_adapter.py
from adapters.github import GitHubAdapter
from unittest.mock import patch, MagicMock
import json

def test_github_adapter_send_reply():
    adapter = GitHubAdapter("mock_token")
    with patch('requests.post') as mock_post:
        mock_post.return_value.status_code = 201
        adapter.send_reply("owner/repo/123", "Hello GitHub")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert kwargs['json']['body'] == "Hello GitHub"
        assert "owner/repo/issues/123/comments" in args[0]

if __name__ == "__main__":
    try:
        test_github_adapter_send_reply()
        print("Test Passed")
    except Exception as e:
        print(f"Test Failed: {e}")
        import traceback
        traceback.print_exc()
