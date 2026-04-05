"""GitHub adapter for the Shadow Poller."""

import requests
from typing import List, Dict

class GitHubAdapter:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://api.github.com"
        self.source = "github"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json"
        }

    def get_mentions(self, last_poll_at: str) -> List[Dict]:
        """Fetch all issue/PR mentions since the last poll timestamp."""
        # For Phase 2, we implement a basic notification-based mention detection.
        # last_poll_at is ISO timestamp.
        return []

    def send_reply(self, issue_id: str, text: str):
        """Post a comment on a GitHub issue or PR.
        issue_id format: owner/repo/issue_number
        """
        if issue_id.count("/") < 2:
            print(f"GitHubAdapter: Invalid issue_id format: {issue_id}")
            return
            
        try:
            owner, repo, issue_num = issue_id.split("/", 2)
        except ValueError:
            print(f"GitHubAdapter: Failed to split issue_id: {issue_id}")
            return
            
        url = f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_num}/comments"
        resp = requests.post(url, headers=self.headers, json={"body": text})
        
        if not resp.ok:
            print(f"GitHubAdapter Error: {resp.text}")
        else:
            print(f"GitHubAdapter: Comment sent to {issue_id}")
    
    def trigger_code_fix(self, repo: str, issue_id: str, prompt: str):
        """Trigger a local coding agent (e.g., Claude Code) to fix the issue."""
        # This will be handled in poller.py dispatcher
        pass
