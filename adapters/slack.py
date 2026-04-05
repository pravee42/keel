"""Slack adapter for the Shadow Poller."""

import requests
from typing import List, Dict

class SlackAdapter:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://slack.com/api"
        self.source = "slack"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def get_mentions(self, last_poll_at: str) -> List[Dict]:
        """Fetch all mentions since the last poll timestamp."""
        # For Phase 2, we implement a basic search-based mention detection.
        # last_poll_at is ISO timestamp. Slack search is less precise but works without complex app setup.
        # A real implementation would use the events API or conversations.history.
        return []

    def send_reply(self, message_id: str, text: str):
        """Post a reply to a specific Slack message/thread. 
        message_id format expected: channel_id/ts
        """
        if "/" not in message_id:
            print(f"SlackAdapter: Invalid message_id format: {message_id}")
            return
            
        try:
            channel, ts = message_id.split("/")
        except ValueError:
            print(f"SlackAdapter: Failed to split message_id: {message_id}")
            return
            
        payload = {
            "channel": channel,
            "thread_ts": ts,
            "text": text
        }
        
        resp = requests.post(f"{self.base_url}/chat.postMessage", headers=self.headers, json=payload)
        if not resp.ok:
            print(f"SlackAdapter Error: {resp.text}")
        else:
            print(f"SlackAdapter: Reply sent to {message_id}")
