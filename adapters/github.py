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
        """Fetch all issue/PR mentions since the last poll timestamp using Notifications API."""
        # last_poll_at is ISO timestamp. GitHub notifications API supports 'since'.
        params = {"since": last_poll_at, "all": True}
        resp = requests.get(f"{self.base_url}/notifications", headers=self.headers, params=params)
        
        if not resp.ok:
            print(f"GitHubAdapter Error: {resp.text}")
            return []
            
        notifications = resp.json()
        mentions = []
        for n in notifications:
            if n.get("reason") in ("mention", "team_mention"):
                subject = n.get("subject", {})
                url = subject.get("url", "")
                if "issues" in url or "pulls" in url:
                    # Extract owner/repo/number
                    # subject['url'] format: https://api.github.com/repos/owner/repo/issues/1
                    parts = url.split("/")
                    if len(parts) >= 4:
                        owner = parts[-4]
                        repo = parts[-3]
                        num = parts[-1]
                        mid = f"{owner}/{repo}/{num}"
                        
                        mentions.append({
                            "id": mid,
                            "text": subject.get("title", "No title"),
                            "source": self.source,
                            "url": url
                        })
        return mentions

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
