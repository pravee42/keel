"""Background service for polling external platforms for developer mentions."""

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict

import config as cfg
import shadow_agent
import profile as profile_mod
from adapters.slack import SlackAdapter
from adapters.github import GitHubAdapter

STATE_FILE = Path.home() / ".keel" / "polling_state.json"

def load_state() -> Dict:
    """Load the last poll timestamp and processed IDs."""
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {
        "last_poll_at": datetime.now(timezone.utc).isoformat(),
        "processed_ids": []
    }

def save_state(state: Dict):
    """Save the polling state."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))

def run_poller_once():
    """Execute one polling cycle across all adapters."""
    current_cfg = cfg.load()
    state = load_state()
    last_poll = state["last_poll_at"]
    processed = set(state["processed_ids"])
    
    # Load Persona
    persona = profile_mod.load_persona()
    if not persona:
        print("Poller: No persona found. Skipping cycle.")
        return

    # Platforms and Adapters
    adapters = []
    
    # Slack
    slack_token = current_cfg.get("api_keys", {}).get("slack")
    if slack_token:
        adapters.append(SlackAdapter(slack_token))
    
    # GitHub
    github_token = current_cfg.get("api_keys", {}).get("github")
    if github_token:
        adapters.append(GitHubAdapter(github_token))

    # Cycle through adapters
    all_mentions = []
    for adapter in adapters:
        try:
            mentions = adapter.get_mentions(last_poll)
            all_mentions.extend(mentions)
        except Exception as e:
            print(f"Poller: Adapter error: {e}")

    # Process mentions
    new_processed = []
    for m in all_mentions:
        mid = f"{m.get('source')}:{m.get('id')}"
        if mid in processed:
            continue
        
        print(f"Poller: Analyzing mention {mid}...")
        analysis = shadow_agent.analyze_mention(m.get("text", ""), persona)
        
        if analysis.get("confidence", 0) >= 100:
            action = analysis.get("action")
            if action == "reply":
                print(f"Poller: Replying to {mid}...")
                for adapter in adapters:
                    if adapter.source == m.get("source"):
                        adapter.send_reply(m.get("id"), analysis.get("response_text"))
                        break
            elif action == "code":
                print(f"Poller: Triggering code fix for {mid}...")
                # Execution of code fixes would involve running shell commands in specific repos
                pass
            
            processed.add(mid)
            new_processed.append(mid)

    # Update state
    state["last_poll_at"] = datetime.now(timezone.utc).isoformat()
    # Keep only the last 1000 processed IDs to avoid bloat
    state["processed_ids"] = list(processed)[-1000:]
    save_state(state)

def main_loop():
    """Background loop that runs indefinitely."""
    print("Keel Shadow Poller started. Polling every 60 seconds...")
    while True:
        try:
            run_poller_once()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Poller Loop Error: {e}")
        time.sleep(60)

if __name__ == "__main__":
    main_loop()
