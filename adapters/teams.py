"""Microsoft Teams adapter for the Shadow Poller."""

import requests
from typing import List, Dict

class TeamsAdapter:
    def __init__(self, token: str):
        self.token = token
        self.base_url = "https://graph.microsoft.com/v1.0"
        self.source = "teams"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def get_mentions(self, last_poll_at: str) -> List[Dict]:
        """Fetch all channel mentions since the last poll timestamp."""
        # For Phase 2, we scaffold this as Teams Graph API is complex for polling.
        return []

    def send_reply(self, message_id: str, text: str):
        """Post a reply to a specific Teams message.
        message_id format: team_id/channel_id/message_id
        """
        if message_id.count("/") < 2:
            print(f"TeamsAdapter: Invalid message_id format: {message_id}")
            return
            
        try:
            team_id, channel_id, msg_id = message_id.split("/", 2)
        except ValueError:
            print(f"TeamsAdapter: Failed to split message_id: {message_id}")
            return
            
        url = f"{self.base_url}/teams/{team_id}/channels/{channel_id}/messages/{msg_id}/replies"
        payload = {
            "body": {
                "content": text
            }
        }
        resp = requests.post(url, headers=self.headers, json=payload)
        
        if not resp.ok:
            print(f"TeamsAdapter Error: {resp.text}")
        else:
            print(f"TeamsAdapter: Reply sent to {message_id}")
