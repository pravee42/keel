"""Local OpenAI-compatible logging proxy.

Any tool that supports a custom base URL routes through here.
Keel logs the prompt to the queue, then forwards the request transparently.

Usage:
  Set in your tool:  OPENAI_BASE_URL=http://localhost:4422/v1
  Start:             keel proxy start
  Install as daemon: keel proxy install   (macOS LaunchAgent)

Supports both regular and streaming responses (text/event-stream).
No new dependencies — uses only stdlib.
"""

import json
import threading
import uuid
import urllib.request
import urllib.error
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Optional

DEFAULT_PORT = 4422
QUEUE_PATH   = Path.home() / ".keel" / "queue.jsonl"
PID_PATH     = Path.home() / ".keel" / "proxy.pid"


# ─────────────────────────────────────────────
# Queue writer (mirrors queue_writer.py logic, no import needed)
# ─────────────────────────────────────────────

def _enqueue(text: str, source: str = "proxy") -> None:
    """Non-blocking append to queue. Silently ignores any I/O error."""
    try:
        QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "id":        uuid.uuid4().hex[:8],
            "timestamp": datetime.utcnow().isoformat(),
            "source":    source,
            "type":      "prompt",
            "cwd":       "",
            "text":      text[:4000],
            "processed": False,
        }
        with open(QUEUE_PATH, "a") as f:
            f.write(json.dumps(event) + "\n")
    except Exception:
        pass


# ─────────────────────────────────────────────
# HTTP handler
# ─────────────────────────────────────────────

class _ProxyHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length) if length else b""

        # Extract + log prompt before forwarding
        try:
            data     = json.loads(body)
            messages = data.get("messages", [])
            user_msgs = [m for m in messages if m.get("role") == "user"]
            if user_msgs:
                content = user_msgs[-1].get("content", "")
                text    = (
                    " ".join(p.get("text", "") for p in content if isinstance(p, dict))
                    if isinstance(content, list) else str(content)
                )
                if text.strip():
                    _enqueue(text, source=self.server.source_label)
        except Exception:
            pass

        # Forward to real API
        target_url = self.server.forward_url.rstrip("/") + self.path
        fwd_headers = {
            k: v for k, v in self.headers.items()
            if k.lower() not in ("host", "transfer-encoding", "connection", "content-length")
        }
        fwd_headers["Content-Length"] = str(len(body))

        req = urllib.request.Request(
            target_url, data=body, headers=fwd_headers, method="POST"
        )

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                resp_body = resp.read()
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    if k.lower() not in ("transfer-encoding", "connection"):
                        self.send_header(k, v)
                self.send_header("Content-Length", str(len(resp_body)))
                self.end_headers()
                self.wfile.write(resp_body)
        except urllib.error.HTTPError as e:
            body_err = e.read()
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(body_err)
        except Exception as e:
            err = json.dumps({"error": {"message": str(e), "type": "proxy_error"}}).encode()
            self.send_response(502)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(err)))
            self.end_headers()
            self.wfile.write(err)

    def do_GET(self):
        """Health check endpoint: GET /health"""
        if self.path == "/health":
            body = json.dumps({"status": "ok", "forward": self.server.forward_url}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, fmt, *args):
        pass  # suppress per-request stdout noise


# ─────────────────────────────────────────────
# Server lifecycle
# ─────────────────────────────────────────────

def start(
    port: int = DEFAULT_PORT,
    forward_url: str = "https://api.openai.com",
    source_label: str = "proxy",
    block: bool = True,
) -> Optional[threading.Thread]:
    """Start the proxy server.

    block=True  — run in foreground (for `keel proxy start`)
    block=False — run in a background thread (for embedding in other servers)
    """
    server = HTTPServer(("127.0.0.1", port), _ProxyHandler)
    server.forward_url  = forward_url
    server.source_label = source_label

    # Write PID
    PID_PATH.parent.mkdir(parents=True, exist_ok=True)
    PID_PATH.write_text(str(__import__("os").getpid()))

    print(f"keel proxy  →  http://localhost:{port}/v1")
    print(f"  forwarding to: {forward_url}")
    print(f"  set in your tools: OPENAI_BASE_URL=http://localhost:{port}/v1")
    print(f"  health check:  curl http://localhost:{port}/health")

    if block:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nProxy stopped.")
        finally:
            PID_PATH.unlink(missing_ok=True)
        return None
    else:
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        return t


def stop() -> bool:
    """Send SIGTERM to a running proxy started via `keel proxy start`."""
    if not PID_PATH.exists():
        return False
    import os
    import signal
    try:
        pid = int(PID_PATH.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        PID_PATH.unlink(missing_ok=True)
        return True
    except (ProcessLookupError, ValueError):
        PID_PATH.unlink(missing_ok=True)
        return False


def is_running(port: int = DEFAULT_PORT) -> bool:
    """Check if a proxy is already listening on the given port."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0
