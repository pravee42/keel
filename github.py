"""GitHub PR capture — fetch PR descriptions + review comments into the keel queue."""

import json
import os
import re
import subprocess
import uuid
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import config as cfg

GITHUB_API = "https://api.github.com"
QUEUE_PATH = Path.home() / ".keel" / "queue.jsonl"


def get_token() -> Optional[str]:
    """Token lookup: stored config → GITHUB_TOKEN env → GH_TOKEN env."""
    c = cfg.load()
    return (c.get("github_token")
            or os.environ.get("GITHUB_TOKEN")
            or os.environ.get("GH_TOKEN"))


def set_token(token: str) -> None:
    c = cfg.load()
    c["github_token"] = token
    cfg.save(c)


def _api_get(path: str, token: Optional[str] = None):
    url = f"{GITHUB_API}{path}"
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"GitHub API {e.code}: {e.reason} — {body[:200]}")


def detect_repo() -> Optional[str]:
    """Auto-detect owner/repo from git remote origin."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=3,
        )
        if result.returncode != 0:
            return None
        url = result.stdout.strip()
        m = re.search(r'github\.com[:/]([^/]+/[^/\s\.]+?)(?:\.git)?$', url)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def fetch_and_queue(
    repo: str,
    since_days: int = 30,
    pr_number: Optional[int] = None,
    token: Optional[str] = None,
) -> int:
    """Fetch PRs from GitHub and append them to the keel queue. Returns count queued."""
    token = token or get_token()
    since = (datetime.utcnow() - timedelta(days=since_days)).strftime("%Y-%m-%dT%H:%M:%SZ")

    if pr_number:
        prs = [_api_get(f"/repos/{repo}/pulls/{pr_number}", token)]
    else:
        prs = _api_get(
            f"/repos/{repo}/pulls?state=all&sort=updated&direction=desc&per_page=50",
            token,
        )
        prs = [p for p in prs if (p.get("updated_at") or "") >= since]

    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(QUEUE_PATH, "a") as f:
        for pr in prs:
            text = _build_pr_text(pr, repo, token)
            if len(text) < 100:
                continue  # skip trivial / empty PRs

            event = {
                "id": str(uuid.uuid4())[:8],
                "timestamp": pr.get("updated_at", datetime.utcnow().isoformat()),
                "source": "github",
                "type": "pr",
                "cwd": "",
                "text": text[:5000],
                "processed": False,
                "meta": {
                    "repo": repo,
                    "pr_number": pr["number"],
                    "url": pr["html_url"],
                },
            }
            f.write(json.dumps(event) + "\n")
            count += 1
    return count


def _build_pr_text(pr: dict, repo: str, token: Optional[str]) -> str:
    """Compose a single text block from PR title, description, reviews, comments."""
    parts = [f"PR #{pr['number']}: {pr['title']}"]

    body = (pr.get("body") or "").strip()
    if body:
        parts.append(f"\nDescription:\n{body}")

    try:
        reviews = _api_get(f"/repos/{repo}/pulls/{pr['number']}/reviews", token)
        for r in reviews:
            b = (r.get("body") or "").strip()
            if b and len(b) > 60:
                parts.append(f"\nReview ({r['state']}) by {r['user']['login']}:\n{b}")
    except Exception:
        pass

    try:
        comments = _api_get(f"/repos/{repo}/issues/{pr['number']}/comments", token)
        for c in comments:
            b = (c.get("body") or "").strip()
            if b and len(b) > 80:
                parts.append(f"\nComment by {c['user']['login']}:\n{b}")
    except Exception:
        pass

    return "\n".join(parts)


def list_repos_with_prs(token: Optional[str] = None) -> list:
    """List repos the authenticated user has contributed PRs to (requires token)."""
    token = token or get_token()
    if not token:
        return []
    try:
        data = _api_get("/user/repos?type=all&per_page=50&sort=updated", token)
        return [r["full_name"] for r in data if r.get("open_issues_count", 0) > 0
                or r.get("has_issues")][:20]
    except Exception:
        return []
