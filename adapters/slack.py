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
        """Fetch all mentions since the last poll timestamp using Slack search."""
        # Convert ISO timestamp to a format search can understand or just filter results
        # For simplicity, we search for mentions of the user. 
        # A more robust way is to use the auth.test to get the user ID first.
        
        # 1. Get current user ID
        test_resp = requests.get(f"{self.base_url}/auth.test", headers=self.headers)
        if not test_resp.ok:
            print(f"SlackAdapter Error: {test_resp.text}")
            return []
        user_id = test_resp.json().get("user_id")
        
        # 2. Search for mentions
        query = f"<@{user_id}>"
        search_resp = requests.get(f"{self.base_url}/search.messages", headers=self.headers, params={"query": query, "sort": "timestamp"})
        if not search_resp.ok:
            print(f"SlackAdapter Error: {search_resp.text}")
            return []
            
        messages = search_resp.json().get("messages", {}).get("matches", [])
        mentions = []
        for msg in messages:
            # message_id for Slack is channel_id/ts
            mid = f"{msg.get('channel', {}).get('id')}/{msg.get('ts')}"
            mentions.append({
                "id": mid,
                "text": msg.get("text"),
                "source": self.source,
                "user": msg.get("username") or msg.get("user")
            })
        return mentions

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
