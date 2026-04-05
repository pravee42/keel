"""keel web GUI — Flask server exposing all keel features in a browser."""

import json
import io
import os
import queue
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, Response, send_file,
)

import store
import processor as proc
import config as cfg
import regret as regret_mod
import cost as cost_mod
import profile as profile_mod
import team as team_mod
import github as github_mod
import llm
import projects as projects_mod

DEFAULT_PORT = 5005

app = Flask(__name__, template_folder="templates")
app.secret_key = os.urandom(24)


# ─────────────────────────────────────────────
# Template helpers
# ─────────────────────────────────────────────

@app.context_processor
def inject_globals():
    return {"port": _current_port}


app.jinja_env.filters["basename"] = lambda p: Path(p).name if p else ""

_current_port = DEFAULT_PORT


def _decision_view(d):
    """Enrich a Decision for template use."""
    return {
        "id":             d.id,
        "timestamp":      d.timestamp,
        "domain":         d.domain,
        "title":          d.title,
        "context":        d.context,
        "options":        d.options,
        "choice":         d.choice,
        "reasoning":      d.reasoning,
        "outcome":        d.outcome,
        "outcome_quality": d.outcome_quality,
        "project":        d.project,
        "tags_list":      json.loads(d.tags) if d.tags else [],
        "principles_list": json.loads(d.principles) if d.principles else [],
    }


# ─────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────

@app.route("/")
def index():
    decisions = store.get_all()
    domains = list({d.domain for d in decisions})

    # Regret score
    score_data = regret_mod.get_score()
    regret_score = score_data.get("score")
    regret_trend = score_data.get("trend", "—")
    pending_items = regret_mod.get_pending()

    # Cost
    cost_data = cost_mod.get_summary(since_days=30)

    # Queue
    queue_pending = 0
    if proc.QUEUE_PATH.exists():
        lines = proc.QUEUE_PATH.read_text().strip().split("\n")
        events = [json.loads(l) for l in lines if l.strip()]
        queue_pending = sum(1 for e in events if not e.get("processed"))

    stats = {
        "total":          len(decisions),
        "domains":        domains,
        "regret_score":   regret_score,
        "regret_trend":   regret_trend,
        "regret_pending": len(pending_items),
        "cost_30d":       cost_data["total_cost"],
        "llm_calls":      len(cost_data["records"]),
        "queue_pending":  queue_pending,
    }
    recent = [_decision_view(d) for d in decisions[:8]]
    return render_template("index.html", active="dashboard", stats=stats,
                           recent_decisions=recent)


# ─────────────────────────────────────────────
# Decisions
# ─────────────────────────────────────────────

@app.route("/decisions")
def decisions_list():
    all_d = store.get_all()
    views = [_decision_view(d) for d in all_d]
    domains = sorted({d["domain"] for d in views})
    all_tags = sorted({t for v in views for t in v["tags_list"]})
    return render_template("decisions.html", active="decisions",
                           decisions=views, domains=domains, all_tags=all_tags)


@app.route("/decisions/<did>")
def decision_detail(did):
    d = store.get_by_id(did)
    if not d:
        flash("Decision not found.", "error")
        return redirect(url_for("decisions_list"))
    diff_text = proc.get_diff(did)
    return render_template("decision_detail.html", active="decisions",
                           d=_decision_view(d), diff_text=diff_text)


@app.route("/decisions/<did>/outcome", methods=["POST"])
def save_outcome(did):
    text = request.form.get("text", "").strip()
    if text:
        store.update_outcome(did, text)
        flash("Outcome saved.", "success")
    return redirect(url_for("decision_detail", did=did))


@app.route("/decisions/<did>/quality", methods=["POST"])
def rate_quality(did):
    quality = request.json.get("quality", "")
    if quality in ("good", "neutral", "bad"):
        store.update_outcome_quality(did, quality)
    return jsonify({"ok": True})


@app.route("/decisions/<did>/delete", methods=["POST"])
def delete_decision(did):
    store.delete(did)
    # Remove diff sidecar if present
    sidecar = Path.home() / ".keel" / "diffs" / f"{did}.txt"
    if sidecar.exists():
        sidecar.unlink()
    flash("Decision deleted.", "success")
    return redirect(url_for("decisions_list"))


@app.route("/decisions/<did>/edit")
def edit_decision(did):
    d = store.get_by_id(did)
    if not d:
        flash("Decision not found.", "error")
        return redirect(url_for("decisions_list"))
    return render_template("decision_edit.html", active="decisions", d=_decision_view(d))


@app.route("/decisions/<did>/edit", methods=["POST"])
def save_edit(did):
    d = store.get_by_id(did)
    if not d:
        flash("Decision not found.", "error")
        return redirect(url_for("decisions_list"))
    d.title     = request.form.get("title",     d.title)
    d.domain    = request.form.get("domain",    d.domain)
    d.context   = request.form.get("context",   d.context)
    d.options   = request.form.get("options",   d.options)
    d.choice    = request.form.get("choice",    d.choice)
    d.reasoning = request.form.get("reasoning", d.reasoning)
    store.update_decision(d)
    flash("Decision updated.", "success")
    return redirect(url_for("decision_detail", did=did))


# ─────────────────────────────────────────────
# Process (with SSE streaming)
# ─────────────────────────────────────────────

@app.route("/process")
def process_page():
    queue_stats = {"pending": 0, "total": 0, "processed": 0}
    recent_events = []
    if proc.QUEUE_PATH.exists():
        lines = [l for l in proc.QUEUE_PATH.read_text().strip().split("\n") if l.strip()]
        events = [json.loads(l) for l in lines]
        queue_stats["total"]     = len(events)
        queue_stats["pending"]   = sum(1 for e in events if not e.get("processed"))
        queue_stats["processed"] = queue_stats["total"] - queue_stats["pending"]
        for e in events[-20:][::-1]:
            recent_events.append({
                "timestamp": e.get("timestamp", ""),
                "source":    e.get("source", ""),
                "processed": e.get("processed", False),
                "preview":   e.get("text", "")[:70].replace("\n", " "),
            })
    return render_template("process.html", active="process",
                           queue_stats=queue_stats, recent_events=recent_events)


@app.route("/api/process/stream")
def process_stream():
    """SSE endpoint — streams processor output line-by-line."""
    do_sync = request.args.get("sync", "false").lower() == "true"

    def generate():
        q: queue.Queue = queue.Queue()

        class _StreamOut(io.TextIOBase):
            def write(self, s):
                for line in s.splitlines():
                    if line.strip():
                        q.put(line)
                return len(s)

        def run():
            import sys
            old_stdout = sys.stdout
            sys.stdout = _StreamOut()
            try:
                proc.process_queue(verbose=True, limit=50)
                if do_sync:
                    q.put("Syncing projects…")
                    projects_mod.sync_all(verbose=True)
            finally:
                sys.stdout = old_stdout
                q.put(None)  # sentinel

        thread = threading.Thread(target=run, daemon=True)
        thread.start()

        while True:
            msg = q.get()
            if msg is None:
                yield "data: __DONE__\n\n"
                break
            yield f"data: {msg}\n\n"

    return Response(generate(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ─────────────────────────────────────────────
# Regret
# ─────────────────────────────────────────────

@app.route("/regret")
def regret_page():
    pending_raw = regret_mod.get_pending()
    pending = []
    for d, diff_text in pending_raw:
        v = _decision_view(d)
        v["diff"] = diff_text
        pending.append(v)

    classified_raw = regret_mod.get_all()
    classified = []
    for e in classified_raw:
        d = store.get_by_id(e.decision_id)
        classified.append({
            "timestamp":      e.timestamp,
            "classification": e.classification,
            "title":          d.title if d else e.decision_id,
            "note":           e.note,
        })

    score_data = regret_mod.get_score()
    return render_template("regret.html", active="regret",
                           pending=pending, classified=classified, score=score_data)


@app.route("/api/regret/<did>/suggest")
def regret_suggest(did):
    d = store.get_by_id(did)
    diff_text = proc.get_diff(did) or ""
    if not d:
        return jsonify({"error": "not found"}), 404
    suggestion = regret_mod.suggest_classification(d, diff_text)
    return jsonify(suggestion)


@app.route("/api/regret/<did>/classify", methods=["POST"])
def regret_classify(did):
    data = request.json
    regret_mod.classify(did, is_growth=data.get("is_growth", True),
                        note=data.get("note", ""))
    return jsonify({"ok": True})


# ─────────────────────────────────────────────
# Cost
# ─────────────────────────────────────────────

@app.route("/cost")
def cost_page():
    days = int(request.args.get("days", 30))
    data = cost_mod.get_summary(since_days=days)
    return render_template("cost.html", active="cost", data=data, days=days)


# ─────────────────────────────────────────────
# Quality
# ─────────────────────────────────────────────

@app.route("/quality")
def quality_page():
    import quality as quality_mod
    decisions = store.get_with_outcomes()
    qs = quality_mod.quick_stats(decisions)
    stats = quality_mod.get_principle_stats()
    return render_template("quality.html", active="quality",
                           qs=qs, principle_stats=stats,
                           decisions=[_decision_view(d) for d in decisions])


# ─────────────────────────────────────────────
# Profile
# ─────────────────────────────────────────────

@app.route("/profile")
def profile_page():
    persona  = profile_mod.load_persona()
    meta_path = Path.home() / ".keel" / "persona_meta.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else None
    stale  = profile_mod.persona_is_stale()
    pending = profile_mod.decisions_since_last_build()
    versions = profile_mod.list_versions()
    return render_template("profile.html", active="profile",
                           persona=persona, meta=meta, stale=stale,
                           pending_count=pending,
                           decision_count=len(store.get_all()),
                           versions=versions)


@app.route("/profile/build", methods=["POST"])
def build_profile():
    name = request.form.get("name", "Developer")
    content = profile_mod.build_persona(name=name)
    if content:
        flash("Persona rebuilt successfully.", "success")
    else:
        flash("Not enough decisions yet (need ≥ 5).", "error")
    return redirect(url_for("profile_page"))


# ─────────────────────────────────────────────
# GitHub
# ─────────────────────────────────────────────

@app.route("/github")
def github_page():
    token = github_mod.get_token()
    token_set     = bool(token)
    token_preview = (token[:10] + "…") if token else ""
    detected_repo = github_mod.detect_repo()
    return render_template("github.html", active="github",
                           token_set=token_set, token_preview=token_preview,
                           detected_repo=detected_repo)


@app.route("/github/token", methods=["POST"])
def save_github_token():
    token = request.form.get("token", "").strip()
    if token:
        github_mod.set_token(token)
        flash("GitHub token saved.", "success")
    return redirect(url_for("github_page"))


@app.route("/api/github/fetch", methods=["POST"])
def api_github_fetch():
    data = request.json
    repo    = (data.get("repo") or "").strip()
    since   = int(data.get("since", 30))
    do_proc = bool(data.get("process", False))

    if not repo:
        repo = github_mod.detect_repo()
    if not repo:
        return jsonify({"error": "No repo specified and could not auto-detect."}), 400

    try:
        count = github_mod.fetch_and_queue(repo=repo, since_days=since)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 400

    processed = False
    if do_proc and count > 0:
        proc.process_queue(verbose=False)
        processed = True

    return jsonify({"queued": count, "processed": processed})


# ─────────────────────────────────────────────
# Team
# ─────────────────────────────────────────────

@app.route("/team")
def team_page():
    members = team_mod.list_members()
    return render_template("team.html", active="team",
                           members=members, my_count=len(store.get_all()))


@app.route("/team/import", methods=["POST"])
def team_import():
    name = request.form.get("name", "").strip()
    f    = request.files.get("file")
    if not name or not f:
        flash("Name and file are required.", "error")
        return redirect(url_for("team_page"))
    try:
        content = f.read().decode("utf-8")
        count = team_mod.import_member(name, content)
        flash(f"Imported {count} decisions from {name}.", "success")
    except Exception as e:
        flash(f"Import failed: {e}", "error")
    return redirect(url_for("team_page"))


@app.route("/team/export")
def team_export():
    data = team_mod.export_decisions()
    buf = io.BytesIO(data.encode("utf-8"))
    return send_file(buf, mimetype="application/json",
                     as_attachment=True, download_name="keel_decisions.json")


@app.route("/team/remove", methods=["POST"])
def team_remove():
    name = request.form.get("name", "").strip()
    if name:
        team_mod.remove_member(name)
        flash(f"Removed {name}.", "success")
    return redirect(url_for("team_page"))


@app.route("/api/team/<name>/conflicts")
def api_team_conflicts(name):
    result = team_mod.find_conflicts(name)
    if result is None:
        return jsonify({"error": f"No data for '{name}'."})
    return jsonify({"result": result})


@app.route("/api/team/persona")
def api_team_persona():
    result = team_mod.build_team_persona()
    if result is None:
        return jsonify({"error": "Not enough data."})
    return jsonify({"result": result})


# ─────────────────────────────────────────────
# Projects
# ─────────────────────────────────────────────

@app.route("/projects")
def projects_list():
    all_projects = store.get_projects()
    views = []
    for p in all_projects:
        root = p["project"]
        if not root:
            continue
        meta = projects_mod.get_project_metadata(root)
        views.append({
            "root":         root,
            "name":         Path(root).name,
            "count":        p["count"],
            "archived":     meta.get("archived", False),
            "confidential": meta.get("confidential", False),
            "last_synced":  meta.get("last_synced_at", ""),
        })
    return render_template("projects.html", active="projects", projects=views)


@app.route("/projects/sync", methods=["POST"])
def sync_project_ui():
    root = request.form.get("root", "").strip()
    if root:
        path = projects_mod.sync_project(root, verbose=True)
        if path:
            flash(f"Synced {Path(root).name}.", "success")
        else:
            flash(f"Sync failed for {Path(root).name}.", "error")
    return redirect(url_for("projects_list"))


@app.route("/projects/toggle", methods=["POST"])
def toggle_project_meta():
    data = request.json
    if not data:
        return jsonify({"error": "No JSON data"}), 400
        
    root = data.get("root", "").strip()
    field = data.get("field", "").strip()
    value = data.get("value")
    
    if root and field in ("archived", "confidential"):
        kwargs = {field: bool(value)}
        projects_mod.set_project_metadata(root, **kwargs)
        return jsonify({"ok": True})
    return jsonify({"error": "invalid"}), 400


# ─────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────

@app.route("/config")
def config_page():
    current_cfg = cfg.load()
    key_status = {}
    for p, info in cfg.PROVIDERS.items():
        stored = current_cfg.get("api_keys", {}).get(p)
        if stored:
            key_status[p] = stored[:8] + "…"
        else:
            import os as _os
            env = _os.environ.get(info["key_env"])
            key_status[p] = "(env var)" if env else ""
    return render_template("config.html", active="config",
                           providers=cfg.PROVIDERS,
                           current_provider=current_cfg.get("provider", "anthropic"),
                           current_model=current_cfg.get("model", ""),
                           key_status=key_status)


@app.route("/config/provider", methods=["POST"])
def save_provider():
    provider = request.form.get("provider", "")
    model    = request.form.get("model", "").strip()
    if provider in cfg.PROVIDERS:
        cfg.set_provider(provider)
    if model:
        cfg.set_model(model)
    flash("Provider configuration saved.", "success")
    return redirect(url_for("config_page"))


@app.route("/config/keys", methods=["POST"])
def save_keys():
    saved = 0
    for p in cfg.PROVIDERS:
        key = request.form.get(f"key_{p}", "").strip()
        if key:
            cfg.set_api_key(p, key)
            saved += 1
    flash(f"{saved} key(s) saved.", "success")
    return redirect(url_for("config_page"))


@app.route("/api/config/test")
def api_config_test():
    ok, msg = llm.test_connection()
    return jsonify({"ok": ok, "message": msg})


# ─────────────────────────────────────────────
# Quality (template)
# ─────────────────────────────────────────────

# quality.html template needed — rendered above via quality_page()


# ─────────────────────────────────────────────
# Start
# ─────────────────────────────────────────────

def run(port: int = DEFAULT_PORT, open_browser: bool = True):
    global _current_port
    _current_port = port
    if open_browser:
        import subprocess
        subprocess.Popen(["open", f"http://localhost:{port}"])
    app.run(port=port, debug=False, threaded=True)
