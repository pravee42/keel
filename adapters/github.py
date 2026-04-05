"""GitHub adapter for the Shadow Poller."""

import requests
from typing import List, Dict

class GitHubAdapter:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"
        self.source = "github"

    def get_mentions(self, last_poll_at: str) -> List[Dict]:
        """Fetch all issue/PR mentions since the last poll timestamp."""
        # Real implementation would use /notifications or /search/issues
        return []

    def send_reply(self, issue_id: str, text: str):
        """Post a comment on a GitHub issue or PR."""
        # Real implementation would use /repos/{owner}/{repo}/issues/{issue_number}/comments
        pass
    
    def trigger_code_fix(self, repo: str, issue_id: str, prompt: str):
        """Trigger a local coding agent (e.g., Claude Code) to fix the issue."""
        # This will be handled in poller.py dispatcher
        pass
