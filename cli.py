#!/usr/bin/env python3
"""keel — git diff for your thinking."""

import json
import subprocess
import tempfile
import time
from datetime import datetime
from typing import Optional

import typer
from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

import analyzer
import store
import processor as proc
import digest as digest_mod
import config as cfg
import llm
import mood as mood_mod
import context as ctx_mod
import review as review_mod
import adr as adr_mod
import debt as debt_mod
import profile as profile_mod
import inject as inject_mod
import service as service_mod
import regret as regret_mod
import proxy as proxy_mod
import projects as projects_mod
import github as github_mod
import cost as cost_mod
import quality as quality_mod
import team as team_mod

app        = typer.Typer(help="Track decisions. Learn your judgment. Flag inconsistencies.")
config_app = typer.Typer(help="Configure LLM provider, model, and API keys.")
app.add_typer(config_app, name="config")
console = Console()

DOMAINS = ["code", "writing", "business", "life", "other"]


def _editor_input(prompt_text: str) -> str:
    """Open $EDITOR for multi-line input."""
    with tempfile.NamedTemporaryFile(suffix=".md", mode="w", delete=False) as f:
        f.write(f"# {prompt_text}\n# (delete this line and write below)\n\n")
        path = f.name
    subprocess.run(["${EDITOR:-vi}", path], shell=True)
    with open(path) as f:
        lines = [l for l in f.readlines() if not l.startswith("#")]
    return "".join(lines).strip()


@app.command()
def log(
    title: str = typer.Option(..., "--title", "-t", prompt="Decision title (one line)"),
    domain: str = typer.Option("other", "--domain", "-d", help=f"Domain: {', '.join(DOMAINS)}"),
):
    """Log a new decision and check it against your history."""
    if domain not in DOMAINS:
        rprint(f"[red]Domain must be one of: {', '.join(DOMAINS)}[/red]")
        raise typer.Exit(1)

    rprint("\n[bold]Describe the situation/context:[/bold]")
    context = typer.prompt("  Context", default="")

    rprint("\n[bold]What options did you consider?[/bold]")
    options = typer.prompt("  Options", default="")

    rprint("\n[bold]What did you decide?[/bold]")
    choice = typer.prompt("  Choice", default="")

    rprint("\n[bold]Why? (your reasoning)[/bold]")
    reasoning = typer.prompt("  Reasoning", default="")

    d = store.Decision(
        id=store.new_id(),
        timestamp=datetime.utcnow().isoformat(),
        domain=domain,
        title=title,
        context=context,
        options=options,
        choice=choice,
        reasoning=reasoning,
        principles="[]",
        outcome="",
    )

    with console.status("[bold green]Extracting principles..."):
        principles = analyzer.extract_principles(d)
        store.update_principles(d.id, principles)
        d.principles = json.dumps(principles)

    store.save(d)
    rprint(f"\n[green]✓ Saved decision [{d.id}][/green]")
    rprint(f"[dim]Principles detected: {', '.join(principles)}[/dim]")

    # Check consistency against history
    history = [h for h in store.get_all() if h.id != d.id]
    if not history:
        rprint("\n[dim]No history yet — this is your first decision.[/dim]")
        return

    with console.status("[bold yellow]Finding similar past decisions..."):
        similar = analyzer.find_similar(d, history)

    if not similar:
        rprint("\n[dim]No similar past decisions found.[/dim]")
        return

    rprint(f"\n[yellow]Found {len(similar)} similar past decision(s):[/yellow]")
    for past, reason in similar:
        rprint(f"  [{past.id}] [bold]{past.title}[/bold] — {reason}")

    with console.status("[bold red]Running consistency check..."):
        diff = analyzer.consistency_diff(d, similar)

    rprint(Panel(diff, title="[bold]Consistency Check[/bold]", border_style="yellow"))


@app.command()
def check(
    title: str = typer.Option(..., "--title", "-t", prompt="What decision are you about to make?"),
    domain: str = typer.Option("other", "--domain", "-d"),
    context: str = typer.Option(..., "--context", "-c", prompt="Context"),
    reasoning: str = typer.Option(..., "--reasoning", "-r", prompt="Your current reasoning"),
):
    """Check a decision BEFORE committing — flags inconsistencies first."""
    d = store.Decision(
        id="__draft__",
        timestamp=datetime.utcnow().isoformat(),
        domain=domain,
        title=title,
        context=context,
        options="",
        choice="(not yet decided)",
        reasoning=reasoning,
        principles="[]",
        outcome="",
    )

    history = store.get_all()
    if not history:
        rprint("[dim]No history yet.[/dim]")
        return

    with console.status("[bold yellow]Scanning history..."):
        similar = analyzer.find_similar(d, history)

    if not similar:
        rprint("[dim]No similar past decisions found. You're in new territory.[/dim]")
        return

    with console.status("[bold red]Diffing against past reasoning..."):
        diff = analyzer.consistency_diff(d, similar)

    rprint(Panel(diff, title="[bold]Pre-Decision Consistency Check[/bold]", border_style="red"))


@app.command()
def diff(
    id1: str = typer.Argument(..., help="First decision ID"),
    id2: str = typer.Argument(..., help="Second decision ID"),
):
    """Explicitly diff the reasoning between two decisions."""
    d1 = store.get_by_id(id1)
    d2 = store.get_by_id(id2)

    if not d1 or not d2:
        rprint("[red]One or both decision IDs not found.[/red]")
        raise typer.Exit(1)

    with console.status("Diffing..."):
        result = analyzer.consistency_diff(d2, [(d1, "explicitly compared")])

    rprint(Panel(result, title=f"[bold]Diff: [{id1}] vs [{id2}][/bold]", border_style="cyan"))


@app.command()
def patterns():
    """Summarize your recurring judgment patterns and reasoning style."""
    decisions = store.get_all()
    if not decisions:
        rprint("[dim]No decisions logged yet.[/dim]")
        return

    with console.status(f"[bold]Analyzing {len(decisions)} decisions..."):
        summary = analyzer.summarize_patterns(decisions)

    rprint(Panel(summary, title="[bold]Your Judgment Patterns[/bold]", border_style="green"))


@app.command()
def ls(domain: Optional[str] = typer.Option(None, "--domain", "-d")):
    """List all logged decisions."""
    decisions = store.get_all()
    if domain:
        decisions = [d for d in decisions if d.domain == domain]

    if not decisions:
        rprint("[dim]No decisions found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="dim", width=10)
    table.add_column("Date", width=12)
    table.add_column("Domain", width=10)
    table.add_column("Title")
    table.add_column("Choice", width=30)

    for d in decisions:
        date = d.timestamp[:10]
        table.add_row(d.id, date, d.domain, d.title, d.choice[:30])

    console.print(table)


@app.command()
def show(decision_id: str = typer.Argument(...)):
    """Show full details of a decision."""
    d = store.get_by_id(decision_id)
    if not d:
        rprint(f"[red]Decision {decision_id} not found.[/red]")
        raise typer.Exit(1)

    rprint(Panel(
        f"[bold]Title:[/bold] {d.title}\n"
        f"[bold]Domain:[/bold] {d.domain}\n"
        f"[bold]Date:[/bold] {d.timestamp[:10]}\n\n"
        f"[bold]Context:[/bold]\n{d.context}\n\n"
        f"[bold]Options considered:[/bold]\n{d.options}\n\n"
        f"[bold]Choice:[/bold]\n{d.choice}\n\n"
        f"[bold]Reasoning:[/bold]\n{d.reasoning}\n\n"
        f"[bold]Principles:[/bold] {', '.join(json.loads(d.principles))}\n\n"
        + (f"[bold]Outcome:[/bold]\n{d.outcome}" if d.outcome else "[dim]No outcome recorded yet.[/dim]"),
        title=f"Decision [{d.id}]",
        border_style="blue",
    ))


@app.command()
def outcome(
    decision_id: str = typer.Argument(...),
    text: str = typer.Option(..., "--text", "-t", prompt="How did it turn out?"),
):
    """Record the outcome of a past decision (retrospective)."""
    if not store.get_by_id(decision_id):
        rprint(f"[red]Decision {decision_id} not found.[/red]")
        raise typer.Exit(1)
    store.update_outcome(decision_id, text)
    rprint(f"[green]✓ Outcome recorded for [{decision_id}][/green]")


@app.command()
def remove(
    decision_id: str = typer.Argument(..., help="Decision ID to permanently delete"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
):
    """Permanently delete a misclassified or irrelevant decision."""
    d = store.get_by_id(decision_id)
    if not d:
        rprint(f"[red]Decision {decision_id} not found.[/red]")
        raise typer.Exit(1)

    rprint(f"  [bold]{d.title}[/bold]  [dim][{d.id}] {d.timestamp[:10]} · {d.domain}[/dim]")

    if not yes:
        confirmed = typer.confirm(f"Permanently delete this decision?", default=False)
        if not confirmed:
            rprint("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)

    store.delete(decision_id)

    # Also remove any sidecar diff
    diff_path = __import__("pathlib").Path.home() / ".keel" / "diffs" / f"{decision_id}.txt"
    if diff_path.exists():
        diff_path.unlink()

    rprint(f"[green]✓ Deleted [{decision_id}][/green]")


@app.command()
def correct(
    decision_id: str = typer.Argument(..., help="Decision ID to correct"),
):
    """Interactively correct a misclassified or poorly extracted decision."""
    d = store.get_by_id(decision_id)
    if not d:
        rprint(f"[red]Decision {decision_id} not found.[/red]")
        raise typer.Exit(1)

    rprint(Panel(
        f"[bold]Title:[/bold] {d.title}\n"
        f"[bold]Domain:[/bold] {d.domain}\n"
        f"[bold]Choice:[/bold] {d.choice}\n"
        f"[bold]Reasoning:[/bold] {d.reasoning[:200]}",
        title=f"Current [{d.id}]",
        border_style="dim",
    ))
    rprint("[dim]Press Enter to keep the current value for any field.[/dim]\n")

    domains = ["code", "writing", "business", "life", "other"]
    title     = typer.prompt("Title",     default=d.title)
    domain    = typer.prompt(f"Domain ({'/'.join(domains)})", default=d.domain)
    context   = typer.prompt("Context",   default=d.context)
    options   = typer.prompt("Options",   default=d.options)
    choice    = typer.prompt("Choice",    default=d.choice)
    reasoning = typer.prompt("Reasoning", default=d.reasoning)

    if domain not in domains:
        rprint(f"[yellow]Unknown domain '{domain}', keeping '{d.domain}'[/yellow]")
        domain = d.domain

    d.title     = title
    d.domain    = domain
    d.context   = context
    d.options   = options
    d.choice    = choice
    d.reasoning = reasoning

    store.update_decision(d)

    # Re-extract principles from corrected content
    confirmed = typer.confirm("Re-extract principles from corrected content?", default=True)
    if confirmed:
        with console.status("Re-extracting principles..."):
            principles = analyzer.extract_principles(d)
            store.update_principles(d.id, principles)
        rprint(f"[dim]Principles: {', '.join(principles)}[/dim]")

    rprint(f"[green]✓ Updated [{decision_id}][/green]")


@app.command()
def install(
    all_hooks: bool = typer.Option(True, "--all/--no-all", help="Install all hooks"),
    claude: bool = typer.Option(False, "--claude", help="Only Claude Code hook"),
    git: bool = typer.Option(False, "--git", help="Only Git hook"),
    shell: bool = typer.Option(False, "--shell", help="Only shell wrappers"),
    cron: bool = typer.Option(False, "--cron", help="Only cron job"),
    uninstall: bool = typer.Option(False, "--uninstall", help="Remove all hooks"),
):
    """Install hooks for Claude Code, Git, Gemini CLI, and other AI tools."""
    import install as ins

    if uninstall:
        rprint("[bold red]Uninstalling...[/bold red]")
        ins.uninstall_claude_code()
        ins.uninstall_git_hook()
        return

    specific = claude or git or shell or cron
    rprint("[bold]Installing decide hooks...[/bold]\n")

    if not specific or claude:
        ins.install_claude_code()
    if not specific or git:
        ins.install_git_hook()
    if not specific or shell:
        ins.install_shell_wrappers()
    if not specific or cron:
        ins.install_cron()
        ins.install_launch_agents()

    rprint(f"\n[green]Done.[/green] Queue: [dim]{proc.QUEUE_PATH}[/dim]")
    rprint("Run [bold]keel process[/bold] to process captured events manually.")


@app.command()
def process(
    quiet: bool = typer.Option(False, "--quiet", "-q"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max events to process"),
    sync: bool = typer.Option(False, "--sync", help="Sync all project CLAUDE.md files after processing"),
):
    """Process captured prompts/commits and extract decisions."""
    verbose = not quiet
    if verbose:
        rprint(f"[bold]Processing queue...[/bold] ({proc.QUEUE_PATH})")
    results = proc.process_queue(verbose=verbose, limit=limit)
    if results and verbose:
        saved = [r for r in results if r.get("saved")]
        skipped = [r for r in results if r.get("skipped")]
        rprint(f"\n[green]✓ {len(saved)} decisions saved[/green]  [dim]{len(skipped)} skipped[/dim]")
    if sync:
        if verbose:
            rprint("\n[bold]Syncing project contexts...[/bold]")
        results_sync = projects_mod.sync_all(verbose=verbose)
        if verbose:
            synced = sum(1 for v in results_sync.values() if v)
            rprint(f"[green]✓ {synced} project(s) synced[/green]")


@app.command()
def sync(
    project: Optional[str] = typer.Argument(
        None, help="Project path to sync (default: git root of current directory)"
    ),
    all_projects: bool = typer.Option(False, "--all", "-a", help="Sync all known projects"),
    force: bool = typer.Option(False, "--force", "-f", help="Force sync even if up to date"),
    quiet: bool = typer.Option(False, "--quiet", "-q"),
):
    """Inject per-project decision context into project CLAUDE.md files.

    \b
    keel sync                 # sync current git repo
    keel sync /path/to/repo   # sync a specific repo
    keel sync --all           # sync every known project
    keel sync --force         # re-generate even if not stale
    """
    import subprocess as _sp

    if all_projects:
        if not quiet:
            rprint("[bold]Syncing all known projects...[/bold]")
        results = projects_mod.sync_all(verbose=not quiet)
        synced = sum(1 for v in results.values() if v)
        skipped = len(results) - synced
        if not quiet:
            rprint(f"\n[green]✓ {synced} synced[/green]  [dim]{skipped} already up to date[/dim]")
        return

    # Resolve target
    if project:
        target = project
    else:
        res = _sp.run(["git", "rev-parse", "--show-toplevel"],
                      capture_output=True, text=True)
        if res.returncode != 0:
            rprint("[red]Not inside a git repository.[/red]")
            rprint("[dim]Use --all or provide a project path.[/dim]")
            raise typer.Exit(1)
        target = res.stdout.strip()

    if not quiet:
        rprint(f"[bold]Syncing[/bold] {target}")

    path = (
        projects_mod.sync_project(target, verbose=not quiet)
        if force
        else projects_mod.sync_if_stale(target, quiet=quiet)
    )

    if path:
        if not quiet:
            rprint(f"[green]✓ Injected → {path}[/green]")
    else:
        if not quiet:
            rprint("[dim]Already up to date. Use --force to regenerate.[/dim]")


@app.command("projects")
def projects_cmd(
    sync_all: bool = typer.Option(False, "--sync", "-s", help="Sync all listed projects"),
    remove: Optional[str] = typer.Option(None, "--remove",
                                          help="Remove keel context from project CLAUDE.md"),
):
    """List all projects with tracked decisions and their sync status."""
    if remove:
        removed = projects_mod.remove_project_context(__import__("pathlib").Path(remove))
        if removed:
            rprint(f"[green]✓ Removed keel context from {remove}/CLAUDE.md[/green]")
        else:
            rprint(f"[dim]No keel context found in {remove}/CLAUDE.md[/dim]")
        return

    project_list = store.get_projects()
    if not project_list:
        rprint("[dim]No projects tracked yet.[/dim]")
        rprint("[dim]Projects are detected automatically from git root when decisions are captured.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Project",       style="bold")
    table.add_column("Decisions",     justify="right", width=10)
    table.add_column("Last Activity", width=14)
    table.add_column("Sync",          width=12)
    table.add_column("CLAUDE.md",     width=14)

    for p in project_list:
        root  = p["project"]
        name  = __import__("pathlib").Path(root).name
        stale = projects_mod.is_stale(root)
        sync_color  = "yellow" if stale else "green"
        sync_label  = "stale" if stale else "current"
        claude_path = __import__("pathlib").Path(root) / "CLAUDE.md"
        has_block   = (
            claude_path.exists()
            and projects_mod.MARKER_START in claude_path.read_text()
        )
        inj_str = "[green]injected[/green]" if has_block else "[dim]not injected[/dim]"
        table.add_row(
            f"{name}\n[dim]{root}[/dim]",
            str(p["count"]),
            p["latest"][:10],
            f"[{sync_color}]{sync_label}[/{sync_color}]",
            inj_str,
        )

    console.print(table)

    if sync_all:
        rprint()
        results = projects_mod.sync_all(verbose=True)
        synced = sum(1 for v in results.values() if v)
        rprint(f"\n[green]✓ {synced} project(s) synced[/green]")
    else:
        rprint(f"\n[dim]keel sync --all   to sync all  ·  keel sync   for current project[/dim]")


@app.command()
def daemon(
    interval: int = typer.Option(60, "--interval", "-i", help="Seconds between queue checks"),
):
    """Run as a background daemon — watches queue and processes continuously."""
    rprint(f"[bold]decide daemon[/bold] started (interval: {interval}s)")
    rprint(f"Queue: [dim]{proc.QUEUE_PATH}[/dim]")
    rprint("Ctrl+C to stop\n")
    try:
        while True:
            proc.process_queue(verbose=False)
            time.sleep(interval)
    except KeyboardInterrupt:
        rprint("\n[dim]Stopped.[/dim]")


@app.command()
def queue(
    tail: int = typer.Option(20, "--tail", "-n"),
    show_processed: bool = typer.Option(False, "--all"),
):
    """Show raw captured events in the queue."""
    if not proc.QUEUE_PATH.exists():
        rprint("[dim]Queue is empty.[/dim]")
        return

    lines = proc.QUEUE_PATH.read_text().strip().split("\n")
    events = [json.loads(l) for l in lines if l.strip()]

    if not show_processed:
        events = [e for e in events if not e.get("processed")]

    events = events[-tail:]

    table = Table(show_header=True, header_style="bold")
    table.add_column("Time", width=12)
    table.add_column("Source", width=12)
    table.add_column("Type", width=8)
    table.add_column("Status", width=10)
    table.add_column("Preview")

    for e in events:
        status = "[dim]processed[/dim]" if e.get("processed") else "[yellow]pending[/yellow]"
        preview = e["text"][:60].replace("\n", " ")
        table.add_row(e["timestamp"][11:19], e["source"], e["type"], status, preview)

    console.print(table)


@app.command()
def weekly(
    days: int = typer.Option(7, "--days", "-d", help="How many days back to include"),
    save: bool = typer.Option(True, "--save/--no-save", help="Save digest to ~/.keel/digests/"),
):
    """Generate your weekly thinking digest."""
    from rich.markdown import Markdown

    decisions = store.get_all()
    since = __import__("datetime").datetime.utcnow() - __import__("datetime").timedelta(days=days)
    recent = [d for d in decisions
              if __import__("datetime").datetime.fromisoformat(d.timestamp) >= since]

    if not recent:
        rprint(f"[dim]No decisions in the last {days} days.[/dim]")
        raise typer.Exit(0)

    # Print stats header
    rprint(f"\n[bold]Weekly Digest[/bold] — last {days} days\n")

    with console.status("[bold green]Generating digest..."):
        result = digest_mod.build_digest(days=days)

    if not result:
        rprint("[dim]Nothing to digest.[/dim]")
        return

    s = result["stats"]
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="dim")
    table.add_column(style="bold")
    table.add_row("Total decisions", str(s["total"]))
    table.add_row("Consistent with past", f"[green]{s['consistent']}[/green]")
    table.add_row("Deliberate reversals", f"[cyan]{s['deliberate_reversals']}[/cyan]")
    table.add_row("Unresolved contradictions", f"[yellow]{s['contradictions']}[/yellow]")
    table.add_row("New territory", f"[dim]{s['new_territory']}[/dim]")
    console.print(table)
    rprint()

    console.print(Markdown(result["narrative"]))

    if save:
        from pathlib import Path
        digest_dir = Path.home() / ".keel" / "digests"
        saved = list(digest_dir.glob("*.json"))[-1] if digest_dir.exists() else None
        if saved:
            rprint(f"\n[dim]Saved → {saved}[/dim]")


@app.command()
def resolve(
    decision_id: str = typer.Argument(..., help="Decision ID to mark as resolved"),
    reason: str = typer.Option(..., "--reason", "-r",
                               prompt="Why was this a deliberate reversal?"),
):
    """Mark a flagged contradiction as a deliberate reversal (with your reasoning)."""
    d = store.get_by_id(decision_id)
    if not d:
        rprint(f"[red]Decision {decision_id} not found.[/red]")
        raise typer.Exit(1)

    digest_mod.mark_resolved(decision_id, reason)
    rprint(f"[green]✓ [{decision_id}] marked as deliberate reversal[/green]")
    rprint(f"[dim]Reason: {reason}[/dim]")
    rprint("[dim]This will show up correctly in your next weekly digest.[/dim]")


@app.command("digests")
def list_digests():
    """List past weekly digests."""
    from pathlib import Path
    from rich.markdown import Markdown

    digest_dir = Path.home() / ".keel" / "digests"
    if not digest_dir.exists() or not list(digest_dir.glob("*.json")):
        rprint("[dim]No digests yet. Run: keel weekly[/dim]")
        return

    files = sorted(digest_dir.glob("*.json"), reverse=True)
    for f in files[:10]:
        data = json.loads(f.read_text())
        s = data["stats"]
        rprint(
            f"[bold]{data['period']}[/bold]  "
            f"[dim]{s['total']} decisions · "
            f"[green]{s['consistent']} consistent[/green] · "
            f"[yellow]{s['contradictions']} flagged[/yellow][/dim]"
        )
    rprint(f"\n[dim]Run [bold]keel weekly[/bold] to generate a new one.[/dim]")


@app.command()
def correlate(
    narrative: bool = typer.Option(False, "--narrative", "-n",
                                   help="Generate LLM narrative (slower, richer)"),
    days: int = typer.Option(0, "--days", "-d",
                             help="Limit to last N days (0 = all time)"),
):
    """Show how decision quality correlates with time-of-day and day-of-week."""
    from rich.markdown import Markdown

    decisions = store.get_all()
    if days > 0:
        since = __import__("datetime").datetime.utcnow() - __import__("datetime").timedelta(days=days)
        decisions = [d for d in decisions
                     if __import__("datetime").datetime.fromisoformat(d.timestamp) >= since]

    if len(decisions) < 3:
        rprint("[dim]Need at least 3 decisions to compute correlations.[/dim]")
        raise typer.Exit(0)

    with console.status("Computing correlations..."):
        stats = mood_mod.quick_stats(decisions)

    # ── Time-of-day table ──
    rprint(f"\n[bold]Decision quality by time of day[/bold]  "
           f"[dim]({stats['total_decisions']} decisions, "
           f"{stats['total_flagged']} flagged)[/dim]\n")

    time_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    time_table.add_column("Time slot",  width=30)
    time_table.add_column("Decisions",  justify="right", width=10)
    time_table.add_column("Flagged",    justify="right", width=10)
    time_table.add_column("Flag rate",  justify="right", width=10)
    time_table.add_column("Signal",     width=8)

    for row in stats["time_rows"]:
        rate  = row["rate"]
        color = "red" if rate >= 0.5 else ("yellow" if rate >= 0.25 else "green")
        bar   = "⚠⚠⚠" if rate >= 0.5 else ("⚠⚠ " if rate >= 0.25 else ("⚠  " if rate > 0 else "✓  "))
        time_table.add_row(
            row["condition"],
            str(row["total"]),
            str(row["flagged"]),
            f"[{color}]{rate:.0%}[/{color}]",
            f"[{color}]{bar}[/{color}]",
        )
    console.print(time_table)

    # ── Day type table ──
    rprint("\n[bold]Weekday vs weekend[/bold]\n")
    day_table = Table(show_header=False, box=None, padding=(0, 2))
    day_table.add_column(width=14)
    day_table.add_column(justify="right", width=10)
    day_table.add_column(justify="right", width=10)
    day_table.add_column(justify="right", width=10)

    for row in stats["day_rows"]:
        rate  = row["rate"]
        color = "red" if rate >= 0.5 else ("yellow" if rate >= 0.25 else "green")
        day_table.add_row(
            row["condition"],
            f"{row['total']} decisions",
            f"{row['flagged']} flagged",
            f"[{color}]{rate:.0%}[/{color}]",
        )
    console.print(day_table)

    # ── Worst conditions callout ──
    if stats["worst"]:
        rprint("\n[bold yellow]Highest-risk conditions[/bold yellow]")
        for dim, cond, rate, total in stats["worst"]:
            rprint(f"  [yellow]⚠[/yellow]  [bold]{cond}[/bold]  "
                   f"[dim]{rate:.0%} flag rate across {total} decisions[/dim]")

    # ── Optional LLM narrative ──
    if narrative:
        rprint()
        with console.status("[bold]Generating narrative analysis..."):
            report = mood_mod.generate_mood_report(decisions)
        if report:
            rprint(Panel(
                __import__("rich.markdown", fromlist=["Markdown"]).Markdown(report),
                title="[bold]Mood Correlation Analysis[/bold]",
                border_style="magenta",
            ))
    else:
        rprint(f"\n[dim]Add --narrative for a full LLM-written analysis.[/dim]")


# ─────────────────────────────────────────────
# DevEx features
# ─────────────────────────────────────────────

@app.command()
def context(
    path: Optional[str] = typer.Option(None, "--path", "-p",
                                        help="File/module path for re-onboarding context"),
    inject: bool = typer.Option(False, "--inject",
                                help="Write into CLAUDE.md for automatic injection"),
    project: Optional[str] = typer.Option(None, "--project",
                                           help="Project path for --inject (default: global)"),
    save: bool = typer.Option(False, "--save", help="Save to ~/.keel/system_prompt.md"),
):
    """Generate a personalized system prompt from your decision history.

    Without --path: full profile for injecting into any AI session.
    With --path: module-level context for re-onboarding to specific code.
    """
    from rich.markdown import Markdown

    decisions = store.get_all()

    if path:
        rprint(f"\n[bold]Decision context for:[/bold] {path}\n")
        with console.status("Scanning decision history..."):
            result = ctx_mod.module_context(path, decisions)
        console.print(Markdown(result))
    else:
        rprint("\n[bold]Generating your development profile...[/bold]\n")
        with console.status("Analyzing decision history..."):
            result = ctx_mod.generate_system_prompt(decisions)
        console.print(Markdown(result))

        if save:
            p = ctx_mod.save_system_prompt(result)
            rprint(f"\n[green]✓ Saved → {p}[/green]")

        if inject:
            project_path = __import__("pathlib").Path(project) if project else None
            p = ctx_mod.inject_into_claude_code(result, project_path)
            rprint(f"\n[green]✓ Injected into {p}[/green]")
            rprint("[dim]Claude Code will now use your profile as context.[/dim]")
        else:
            rprint("\n[dim]Tip: --inject writes this into CLAUDE.md for automatic use in Claude Code[/dim]")


@app.command()
def review(
    diff_file: Optional[str] = typer.Option(None, "--diff", "-d",
                                             help="Path to diff file (default: git diff HEAD)"),
    base: str = typer.Option("HEAD", "--base", "-b", help="Git base ref for diff"),
    path: Optional[str] = typer.Option(None, "--path", "-p", help="Limit diff to this path"),
):
    """Review a git diff against your decision history. Flags drifts and contradictions."""
    from rich.markdown import Markdown

    if diff_file:
        diff_text = __import__("pathlib").Path(diff_file).read_text()
    else:
        with console.status("Getting git diff..."):
            diff_text = review_mod.get_git_diff(base=base, path=path)

    if not diff_text.strip():
        rprint("[dim]No changes found.[/dim]")
        raise typer.Exit(0)

    lines = diff_text.count("\n")
    rprint(f"\n[bold]Reviewing diff[/bold] ({lines} lines) against your decision history...\n")

    with console.status("[bold yellow]Cross-referencing decisions..."):
        result = review_mod.review_diff(diff_text)

    console.print(Panel(Markdown(result), title="[bold]Pre-PR Decision Review[/bold]",
                         border_style="yellow"))


@app.command()
def adr(
    decision_id: Optional[str] = typer.Argument(None,
                                                  help="Generate ADR for a specific decision ID"),
    auto: bool = typer.Option(False, "--auto",
                               help="Auto-generate ADRs for all arch decisions without one"),
    adr_dir: Optional[str] = typer.Option(None, "--dir", help="Output directory (default: docs/decisions/)"),
    ls: bool = typer.Option(False, "--list", "-l", help="List existing ADRs"),
):
    """Generate Architecture Decision Records from your decision history."""
    from rich.markdown import Markdown
    from pathlib import Path

    out_dir = Path(adr_dir) if adr_dir else None

    if ls:
        adrs = adr_mod.list_adrs(out_dir)
        if not adrs:
            rprint("[dim]No ADRs found in docs/decisions/[/dim]")
            return
        table = Table(show_header=True, header_style="bold")
        table.add_column("File", style="dim")
        table.add_column("Title")
        table.add_column("Date", width=12)
        table.add_column("Status", width=12)
        for a in adrs:
            table.add_row(a["file"], a["title"], a["date"], a["status"])
        console.print(table)
        return

    if decision_id:
        d = store.get_by_id(decision_id)
        if not d:
            rprint(f"[red]Decision {decision_id} not found.[/red]")
            raise typer.Exit(1)
        with console.status(f"Generating ADR for [{decision_id}]..."):
            content, path = adr_mod.generate_adr(d, out_dir)
        rprint(f"[green]✓ ADR written → {path}[/green]")
        rprint()
        console.print(Markdown(content))
        return

    if auto:
        decisions = store.get_all()
        candidates = [d for d in decisions if adr_mod.should_generate_adr(d)]
        if not candidates:
            rprint("[dim]No architectural decisions found to generate ADRs for.[/dim]")
            return
        rprint(f"[bold]Found {len(candidates)} architectural decisions[/bold]\n")
        for d in candidates:
            with console.status(f"  [{d.id}] {d.title}..."):
                _, path = adr_mod.generate_adr(d, out_dir)
            rprint(f"  [green]✓[/green] {path.name}")
        return

    rprint("Use [bold]decide adr <id>[/bold] or [bold]decide adr --auto[/bold]")


@app.command()
def debt(
    domain: Optional[str] = typer.Option(None, "--domain", "-d"),
    narrative: bool = typer.Option(False, "--narrative", "-n",
                                    help="LLM-written prioritized analysis"),
):
    """Show tech debt — decisions made under pressure, uncertainty, or as compromises."""
    from rich.markdown import Markdown

    with console.status("Scanning for tech debt..."):
        decisions = debt_mod.get_debt_decisions(domain=domain)

    if not decisions:
        rprint("[green]No tech debt decisions found.[/green]")
        rprint("[dim](Decisions get tagged automatically when pressure/uncertainty signals are detected)[/dim]")
        return

    rprint(f"\n[bold]Tech Debt[/bold]  [dim]{len(decisions)} decisions[/dim]\n")

    rows = debt_mod.quick_debt_table(decisions)
    table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
    table.add_column("Score", justify="right", width=7)
    table.add_column("ID",    style="dim",     width=10)
    table.add_column("Date",                   width=12)
    table.add_column("Domain",                 width=10)
    table.add_column("Title")
    table.add_column("Tags",   style="dim")

    for r in rows:
        score_color = "red" if r["score"] >= 6 else ("yellow" if r["score"] >= 3 else "dim")
        table.add_row(
            f"[{score_color}]{r['score']}[/{score_color}]",
            r["id"],
            r["date"],
            r["domain"],
            r["title"],
            ", ".join(r["tags"]),
        )
    console.print(table)

    if narrative:
        rprint()
        with console.status("Generating debt analysis..."):
            report = debt_mod.generate_debt_report(decisions)
        console.print(Panel(Markdown(report), title="[bold]Tech Debt Analysis[/bold]",
                             border_style="red"))
    else:
        rprint(f"\n[dim]Add --narrative for prioritized LLM analysis.[/dim]")


# ─────────────────────────────────────────────
# Regret Minimization Score
# ─────────────────────────────────────────────

@app.command()
def regret(
    pending:  bool = typer.Option(False, "--pending", "-p",
                                  help="List unclassified flagged decisions"),
    ls:       bool = typer.Option(False, "--list",    "-l",
                                  help="List all classified decisions"),
    score:    bool = typer.Option(False, "--score",   "-s",
                                  help="Show your Regret Minimization Score"),
    narrative: bool = typer.Option(False, "--narrative", "-n",
                                   help="LLM-written analysis of your change-of-mind pattern"),
    growth:   Optional[str] = typer.Option(None, "--growth",
                                           help="Classify decision <id> as deliberate growth"),
    regret_id: Optional[str] = typer.Option(None, "--regret",
                                             help="Classify decision <id> as accidental regret"),
    note:     str = typer.Option("", "--note", help="Why — your reasoning for this classification"),
):
    """Track deliberate vs accidental changes of mind. Build your Regret Minimization Score.

    \b
    Workflow:
      keel regret --pending               # interactive review with AI suggestions
      keel regret --score                 # see your score + trend
      keel regret --narrative             # LLM analysis
    """
    from rich.markdown import Markdown

    # ── Classify ──
    if growth or regret_id:
        decision_id = growth or regret_id
        is_growth = bool(growth)
        d = store.get_by_id(decision_id)
        if not d:
            rprint(f"[red]Decision {decision_id} not found.[/red]")
            raise typer.Exit(1)
        if not proc.get_diff(decision_id):
            rprint(f"[yellow]No flagged inconsistency found for [{decision_id}].[/yellow]")
            rprint("[dim]Only decisions with flagged contradictions can be classified.[/dim]")
            raise typer.Exit(1)
        regret_mod.classify(decision_id, is_growth=is_growth, note=note)
        label = "[green]↑ growth[/green]" if is_growth else "[red]✗ regret[/red]"
        rprint(f"  {label} [{decision_id}] {d.title}")
        if note:
            rprint(f"  [dim]Note: {note}[/dim]")
        return

    # ── Pending — interactive review ──
    if pending:
        items = regret_mod.get_pending()
        if not items:
            rprint("[green]Nothing pending — all flagged decisions are classified.[/green]")
            return

        rprint(f"\n[bold]Regret review[/bold]  [dim]{len(items)} unclassified[/dim]")
        rprint("[dim]For each decision keel will suggest Growth or Regret. "
               "Pick a suggestion, type your own note, or skip.[/dim]\n")

        classified = 0
        for idx, (d, diff_text) in enumerate(items, 1):
            # Decision header
            console.print(Panel(
                f"[bold]{d.title}[/bold]\n"
                f"[dim]{d.timestamp[:10]} · {d.domain}[/dim]\n\n"
                f"[bold]Choice:[/bold] {d.choice[:150]}\n\n"
                f"[bold]Flagged inconsistency:[/bold]\n"
                f"[dim]{diff_text[:400].strip()}[/dim]",
                title=f"[bold]{idx}/{len(items)}[/bold]  [{d.id}]",
                border_style="yellow",
            ))

            # Fetch LLM suggestion
            with console.status("[dim]Getting suggestion...[/dim]"):
                suggestion = regret_mod.suggest_classification(d, diff_text)

            rec   = suggestion.get("recommendation", "growth")
            conf  = suggestion.get("confidence", 0.5)
            g_why = suggestion.get("growth_reason", "")
            r_why = suggestion.get("regret_reason", "")
            rec_marker = lambda s: " [bold](suggested)[/bold]" if s == rec else ""

            rprint(f"\n  [green][1] Growth[/green]{rec_marker('growth')}   {g_why}")
            rprint(f"  [red][2] Regret[/red]{rec_marker('regret')}   {r_why}")
            rprint(f"  [dim][s] Skip[/dim]\n")

            raw = typer.prompt(
                "  Choose [1/2/s] or type your own note",
                default="s",
                prompt_suffix=" → ",
            ).strip()

            if raw.lower() in ("s", "skip", ""):
                rprint("  [dim]skipped[/dim]\n")
                continue

            # Resolve classification + note
            if raw == "1":
                is_growth, user_note = True, g_why
            elif raw == "2":
                is_growth, user_note = False, r_why
            else:
                # User typed a custom note — ask which bucket it belongs to
                user_note = raw
                bucket = typer.prompt(
                    "  Growth or Regret? [g/r]",
                    default=rec[0],
                    prompt_suffix=" → ",
                ).strip().lower()
                is_growth = bucket.startswith("g")

            regret_mod.classify(d.id, is_growth=is_growth, note=user_note)
            label = "[green]↑ growth[/green]" if is_growth else "[red]✗ regret[/red]"
            rprint(f"  {label}  [dim]{user_note[:80]}[/dim]\n")
            classified += 1

        rprint(f"[bold]Done.[/bold]  {classified} classified, "
               f"{len(items) - classified} skipped.")
        if classified:
            rprint("[dim]Run keel regret --score to see your updated score.[/dim]")
        return

    # ── List classified ──
    if ls:
        entries = regret_mod.get_all()
        if not entries:
            rprint("[dim]Nothing classified yet. Run: keel regret --pending[/dim]")
            return
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("Date",   width=12)
        table.add_column("ID",     style="dim", width=10)
        table.add_column("Type",   width=12)
        table.add_column("Decision")
        table.add_column("Note", style="dim")
        for e in entries:
            d = store.get_by_id(e.decision_id)
            title = d.title if d else e.decision_id
            if e.classification == "growth":
                cls_str = "[green]↑ growth[/green]"
            else:
                cls_str = "[red]✗ regret[/red]"
            table.add_row(e.timestamp[:10], e.decision_id, cls_str, title, e.note[:40])
        console.print(table)
        return

    # ── Score ──
    if score or narrative or (not pending and not ls and not growth and not regret_id):
        data = regret_mod.get_score()
        if data["total"] == 0:
            rprint("[dim]No classifications yet. Run: keel regret --pending[/dim]")
            raise typer.Exit(0)

        # Score display
        pct = data["score"]
        score_color = "green" if pct >= 0.7 else ("yellow" if pct >= 0.4 else "red")
        bar_filled  = int(pct * 20)
        bar = "█" * bar_filled + "░" * (20 - bar_filled)

        rprint(f"\n[bold]Regret Minimization Score[/bold]\n")
        rprint(f"  [{score_color}]{bar}[/{score_color}]  [{score_color}]{pct:.0%}[/{score_color}]  deliberate\n")

        stat_table = Table(show_header=False, box=None, padding=(0, 2))
        stat_table.add_column(style="dim", width=22)
        stat_table.add_column(style="bold")
        stat_table.add_row("Total classified",   str(data["total"]))
        stat_table.add_row("↑ Growth (deliberate)", f"[green]{data['growth']}[/green]")
        stat_table.add_row("✗ Regret (accidental)",  f"[red]{data['regret']}[/red]")
        trend_color = "green" if data["trend"] == "improving" else (
            "red" if data["trend"] == "declining" else "dim")
        stat_table.add_row("Recent trend",
                           f"[{trend_color}]{data['trend']}[/{trend_color}]"
                           + (f"  (recent {data['recent_score']:.0%} vs all-time {pct:.0%})"
                              if data["recent_score"] is not None else ""))
        console.print(stat_table)

        # By-domain breakdown
        if data["by_domain"]:
            rprint("\n[bold]By domain[/bold]")
            dom_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
            dom_table.add_column("Domain",    width=12)
            dom_table.add_column("Growth",    justify="right", width=8)
            dom_table.add_column("Regret",    justify="right", width=8)
            dom_table.add_column("Score",     justify="right", width=8)
            dom_table.add_column("Signal",    width=12)
            for domain, v in sorted(data["by_domain"].items()):
                total_d = v["growth"] + v["regret"]
                d_score = v["growth"] / total_d
                d_color = "green" if d_score >= 0.7 else ("yellow" if d_score >= 0.4 else "red")
                signal  = "deliberate" if d_score >= 0.7 else ("mixed" if d_score >= 0.4 else "drifting")
                dom_table.add_row(
                    domain,
                    f"[green]{v['growth']}[/green]",
                    f"[red]{v['regret']}[/red]",
                    f"[{d_color}]{d_score:.0%}[/{d_color}]",
                    f"[{d_color}]{signal}[/{d_color}]",
                )
            console.print(dom_table)

        # LLM narrative
        if narrative:
            rprint()
            with console.status("Generating analysis..."):
                report = regret_mod.generate_report()
            if report:
                console.print(Panel(
                    Markdown(report),
                    title="[bold]Change-of-Mind Analysis[/bold]",
                    border_style="magenta",
                ))
        else:
            rprint(f"\n[dim]Add --narrative for a full LLM-written analysis.[/dim]")
            rprint(f"[dim]Classify more decisions with: keel regret --pending[/dim]")


# ─────────────────────────────────────────────
# Persona / injection / service commands
# ─────────────────────────────────────────────

@app.command()
def profile(
    build:    bool = typer.Option(False, "--build",    "-b", help="(Re)build the persona document"),
    show:     bool = typer.Option(False, "--show",     "-s", help="Print the current persona"),
    name:     str  = typer.Option("Praveen", "--name", "-n", help="Your name for the document"),
    status:   bool = typer.Option(False, "--status",         help="Show staleness / decision count"),
    versions: bool = typer.Option(False, "--versions",       help="List persona version history"),
    diff:     bool = typer.Option(False, "--diff",           help="Show how your thinking changed (latest 2 versions)"),
    from_date: Optional[str] = typer.Option(None, "--from", help="Older version date for --diff (YYYY-MM-DD)"),
    to_date:   Optional[str] = typer.Option(None, "--to",   help="Newer version date for --diff (YYYY-MM-DD)"),
):
    """Build and display your developer identity (memory clone)."""
    from rich.markdown import Markdown

    if status:
        stale   = profile_mod.persona_is_stale()
        pending = profile_mod.decisions_since_last_build()
        rprint(f"  Persona stale: [{'yellow' if stale else 'green'}]{stale}[/]")
        rprint(f"  Decisions since last build: [bold]{pending}[/bold]")
        return

    if versions:
        vers = profile_mod.list_versions()
        if not vers:
            rprint("[dim]No snapshots yet. A snapshot is saved each time you run --build.[/dim]")
            return
        rprint(f"\n[bold]Persona versions[/bold]  [dim]({len(vers)} snapshots)[/dim]\n")
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("Date",   width=14)
        table.add_column("Size",   justify="right", width=10)
        table.add_column("Path",   style="dim")
        for v in vers:
            table.add_row(v["date"], f"{v['size']:,} bytes", str(v["path"]))
        console.print(table)
        rprint(f"\n[dim]Use --diff to compare the latest two, or --from/--to for specific dates.[/dim]")
        return

    if diff:
        with console.status("Diffing persona versions..."):
            result = profile_mod.diff_versions(date_a=from_date, date_b=to_date)
        if result is None:
            rprint("[yellow]Need at least 2 persona versions to diff.[/yellow]")
            rprint("[dim]Run keel profile --build a second time to create a snapshot.[/dim]")
            raise typer.Exit(0)
        console.print(Panel(
            Markdown(result),
            title="[bold]How your thinking evolved[/bold]",
            border_style="cyan",
        ))
        return

    if build:
        rprint(f"[bold]Building persona for {name}...[/bold]")
        with console.status("Synthesizing identity from decision history..."):
            content = profile_mod.build_persona(name=name)
        if content is None:
            rprint("[yellow]Not enough decisions yet (need ≥ 5).[/yellow]")
            raise typer.Exit(0)
        rprint(f"[green]✓ Persona saved → {profile_mod.PERSONA_PATH}[/green]")
        snap = profile_mod.VERSIONS_DIR
        if snap.exists():
            snaps = list(snap.glob("*.md"))
            if snaps:
                rprint(f"[dim]  snapshot saved → {sorted(snaps)[-1].name}[/dim]")
        console.print(Markdown(content))
        return

    if show:
        content = profile_mod.load_persona()
        if not content:
            rprint("[dim]No persona yet. Run: keel profile --build[/dim]")
            raise typer.Exit(0)
        console.print(Markdown(content))
        return

    # Default: show staleness hint
    content = profile_mod.load_persona()
    if content:
        stale   = profile_mod.persona_is_stale()
        pending = profile_mod.decisions_since_last_build()
        age_str = " [yellow](stale)[/yellow]" if stale else ""
        rprint(f"Persona exists{age_str}  ·  {pending} new decisions since last build")
        rprint("[dim]  --show  ·  --build  ·  --versions  ·  --diff[/dim]")
    else:
        rprint("[dim]No persona yet. Run: keel profile --build[/dim]")


@app.command("inject")
def inject_cmd(
    target: Optional[str] = typer.Option(
        None, "--target", "-t",
        help="Target: claude-code-global | gemini | openai | all (default: all)",
    ),
    remove: bool = typer.Option(False, "--remove", "-r", help="Remove persona from targets"),
    status: bool = typer.Option(False, "--status", "-s", help="Show injection status"),
):
    """Inject your persona into Claude Code, Gemini, and other AI tools."""
    if status:
        st = inject_mod.injection_status()
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("Target", width=22)
        table.add_column("Label",  width=26)
        table.add_column("Status")
        for key, info in inject_mod.TARGETS.items():
            color = "green" if st[key] == "injected" else ("yellow" if "exists" in st[key] else "dim")
            table.add_row(key, info["label"], f"[{color}]{st[key]}[/{color}]")
        console.print(table)
        return

    targets = None if (target is None or target == "all") else [target]

    if remove:
        inject_mod.remove(targets)
        rprint("[green]✓ Persona removed from targets[/green]")
        return

    with console.status("Injecting persona..."):
        results = inject_mod.inject(targets)

    for key, val in results.items():
        label = inject_mod.TARGETS[key]["label"]
        if str(val).startswith("ERROR"):
            rprint(f"  [red]✗[/red] {label}: {val}")
        else:
            rprint(f"  [green]✓[/green] {label} → {val}")


@app.command("service")
def service_cmd(
    action: str = typer.Argument(
        "status", help="Action: install | uninstall | status | trigger"
    ),
    label: Optional[str] = typer.Option(
        None, "--label", "-l",
        help="Agent label for trigger (e.g. com.keel.collector)",
    ),
):
    """Manage macOS LaunchAgent background services."""
    if action == "install":
        rprint("[bold]Installing LaunchAgents...[/bold]")
        service_mod.install_agents(verbose=True)
        rprint(f"\n[green]Done.[/green] Agents will run in the background.")
        rprint(f"[dim]Logs: ~/.keel/com.keel.*.log[/dim]")

    elif action == "uninstall":
        rprint("[bold]Uninstalling LaunchAgents...[/bold]")
        service_mod.uninstall_agents(verbose=True)

    elif action == "status":
        st = service_mod.agent_status()
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("Agent",    width=30)
        table.add_column("Status")
        for lbl, state in st.items():
            color = "green" if state == "running" else ("yellow" if state == "loaded" else "dim")
            table.add_row(lbl, f"[{color}]{state}[/{color}]")
        console.print(table)

    elif action == "trigger":
        lbl = label or "com.keel.collector"
        ok = service_mod.trigger_now(lbl)
        if ok:
            rprint(f"[green]✓ Triggered {lbl}[/green]")
        else:
            rprint(f"[red]✗ Failed to trigger {lbl}[/red]")
            rprint("[dim]Is the agent installed? Run: keel service install[/dim]")
    else:
        rprint(f"[red]Unknown action: {action}[/red]")
        rprint("Valid actions: install | uninstall | status | trigger")
        raise typer.Exit(1)


@app.command()
def proxy(
    action:      str = typer.Argument("status",
                                      help="Action: start | stop | status | install"),
    port:        int = typer.Option(proxy_mod.DEFAULT_PORT, "--port", "-p",
                                    help="Port to listen on"),
    forward_url: str = typer.Option("https://api.openai.com", "--forward", "-f",
                                    help="API to forward requests to"),
):
    """Run a local OpenAI-compatible logging proxy.

    \b
    Any tool that supports a custom base URL can route through keel's proxy.
    Keel logs every prompt before forwarding — no shell wrappers needed.

    \b
    Setup (one time):
      keel proxy start                      # foreground, Ctrl+C to stop
      keel proxy install                    # background LaunchAgent

    \b
    Point your tools at it:
      export OPENAI_BASE_URL=http://localhost:4422/v1
      aider --openai-api-base http://localhost:4422/v1
    """
    if action == "start":
        if proxy_mod.is_running(port):
            rprint(f"[yellow]Proxy already running on port {port}.[/yellow]")
            raise typer.Exit(0)
        proxy_mod.start(port=port, forward_url=forward_url, block=True)

    elif action == "stop":
        if proxy_mod.stop():
            rprint("[green]✓ Proxy stopped[/green]")
        else:
            rprint("[dim]No proxy is running (or PID file missing).[/dim]")

    elif action == "status":
        running = proxy_mod.is_running(port)
        if running:
            rprint(f"[green]● running[/green]  http://localhost:{port}/v1")
            rprint(f"[dim]  health: curl http://localhost:{port}/health[/dim]")
        else:
            rprint(f"[dim]○ not running[/dim]  (port {port})")
            rprint("[dim]  Start with: keel proxy start[/dim]")

    elif action == "install":
        # Add proxy as a third LaunchAgent
        import plistlib
        from pathlib import Path as _Path
        label     = "com.keel.proxy"
        la_dir    = _Path.home() / "Library" / "LaunchAgents"
        plist_path = la_dir / f"{label}.plist"
        import sys as _sys, os as _os
        python = _Path(__file__).parent / ".venv" / "bin" / "python"
        cli    = _Path(__file__)
        plist_data = {
            "Label":            label,
            "ProgramArguments": [str(python), str(cli), "proxy", "start",
                                 "--port", str(port), "--forward", forward_url],
            "StandardOutPath":  str(_Path.home() / ".keel" / f"{label}.log"),
            "StandardErrorPath": str(_Path.home() / ".keel" / f"{label}.err"),
            "RunAtLoad":        True,
            "KeepAlive":        True,
        }
        la_dir.mkdir(parents=True, exist_ok=True)
        with open(plist_path, "wb") as f:
            plistlib.dump(plist_data, f)
        import subprocess as _sp
        _sp.run(["launchctl", "unload", str(plist_path)], capture_output=True)
        result = _sp.run(["launchctl", "load",   str(plist_path)],
                         capture_output=True, text=True)
        if result.returncode == 0:
            rprint(f"[green]✓ {label} installed and started[/green]")
            rprint(f"  listening on http://localhost:{port}/v1")
        else:
            rprint(f"[red]✗ {label}: {result.stderr.strip()}[/red]")
    else:
        rprint(f"[red]Unknown action: {action}[/red]")
        rprint("Valid: start | stop | status | install")
        raise typer.Exit(1)


# ─────────────────────────────────────────────
# Config subcommands
# ─────────────────────────────────────────────

@config_app.callback(invoke_without_command=True)
def config_show(ctx: typer.Context):
    """Show current LLM configuration."""
    if ctx.invoked_subcommand:
        return

    current_cfg = cfg.load()
    provider    = current_cfg.get("provider", "anthropic")
    model       = current_cfg.get("model", "—")
    keys        = current_cfg.get("api_keys", {})

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="dim", width=16)
    table.add_column(style="bold")

    table.add_row("Provider", f"[cyan]{provider}[/cyan]  ({cfg.PROVIDERS[provider]['label']})")
    table.add_row("Model",    model)
    table.add_row("Config",   str(cfg.CONFIG_PATH))
    console.print(table)

    rprint("\n[bold]API keys[/bold]")
    key_table = Table(show_header=False, box=None, padding=(0, 2))
    key_table.add_column(style="dim", width=16)
    key_table.add_column()
    for name, info in cfg.PROVIDERS.items():
        stored = keys.get(name)
        env    = __import__("os").environ.get(info["key_env"])
        if stored:
            status = f"[green]stored[/green]  ({stored[:8]}...)"
        elif env:
            status = f"[yellow]env var[/yellow]  ({info['key_env']})"
        else:
            status = "[dim]not set[/dim]"
        marker = " ◀" if name == provider else ""
        key_table.add_row(name + marker, status)
    console.print(key_table)


@config_app.command("provider")
def config_provider(
    name: str = typer.Argument(..., help=f"Provider: {', '.join(cfg.PROVIDERS)}"),
):
    """Switch the active LLM provider."""
    try:
        old = cfg.get_provider()
        cfg.set_provider(name)
        new_model = cfg.PROVIDERS[name]["default_model"]
        rprint(f"[green]✓ Provider: [bold]{old}[/bold] → [bold]{name}[/bold][/green]")
        rprint(f"  Model set to default: [dim]{new_model}[/dim]")

        # Warn if no key is set
        if not cfg.get_api_key(name):
            env = cfg.PROVIDERS[name]["key_env"]
            rprint(f"\n[yellow]⚠ No API key for {name}.[/yellow]")
            rprint(f"  Run: [bold]keel config key {name} <your-key>[/bold]")
            rprint(f"  Or set env: [dim]export {env}=<your-key>[/dim]")
    except ValueError as e:
        rprint(f"[red]{e}[/red]")
        raise typer.Exit(1)


@config_app.command("model")
def config_model(
    name: str = typer.Argument(..., help="Model name for the current provider"),
):
    """Set the model for the current provider."""
    provider = cfg.get_provider()
    cfg.set_model(name)
    rprint(f"[green]✓ Model → [bold]{name}[/bold][/green]  (provider: {provider})")

    # Show known models as a hint
    known = cfg.PROVIDERS[provider]["models"]
    if name not in known:
        rprint(f"  [dim]Note: not in known list. Known: {', '.join(known)}[/dim]")


@config_app.command("key")
def config_key(
    provider: str = typer.Argument(..., help=f"Provider: {', '.join(cfg.PROVIDERS)}"),
    key: str      = typer.Argument(..., help="API key value"),
):
    """Store an API key for a provider."""
    try:
        cfg.set_api_key(provider, key)
        rprint(f"[green]✓ API key saved for [bold]{provider}[/bold][/green]  ({key[:8]}...)")
    except ValueError as e:
        rprint(f"[red]{e}[/red]")
        raise typer.Exit(1)


@config_app.command("models")
def config_models(
    provider: Optional[str] = typer.Argument(None, help="Provider to list (default: all)"),
):
    """List known models for a provider (or all providers)."""
    providers = [provider] if provider else list(cfg.PROVIDERS)

    for p in providers:
        if p not in cfg.PROVIDERS:
            rprint(f"[red]Unknown provider: {p}[/red]")
            continue
        info    = cfg.PROVIDERS[p]
        current = cfg.get_model() if cfg.get_provider() == p else None
        rprint(f"\n[bold]{info['label']}[/bold]  [dim]({p})[/dim]")
        for m in info["models"]:
            marker = " [green]◀ active[/green]" if m == current else ""
            rprint(f"  {m}{marker}")


@config_app.command("test")
def config_test():
    """Test the current provider config with a quick API call."""
    provider = cfg.get_provider()
    model    = cfg.get_model()
    rprint(f"Testing [bold]{provider}[/bold] / [bold]{model}[/bold]...")

    ok, result = llm.test_connection()
    if ok:
        rprint(f"[green]✓ Connected[/green]  response: [dim]{result}[/dim]")
    else:
        rprint(f"[red]✗ Failed[/red]\n{result}")
        raise typer.Exit(1)


# ─────────────────────────────────────────────
# Feature 9: GitHub PR capture
# ─────────────────────────────────────────────

@app.command("github")
def github_cmd(
    action: str = typer.Argument("fetch", help="Action: fetch | config | detect"),
    repo: Optional[str] = typer.Option(None, "--repo", "-r",
                                       help="GitHub repo (owner/repo). Auto-detected if omitted."),
    since: int = typer.Option(30, "--since", "-d", help="Fetch PRs updated within last N days"),
    pr_number: Optional[int] = typer.Option(None, "--pr", help="Fetch a single PR by number"),
    process: bool = typer.Option(False, "--process", "-p",
                                 help="Run keel process immediately after fetching"),
    token: Optional[str] = typer.Option(None, "--token", help="GitHub token (or set via GITHUB_TOKEN)"),
):
    """Capture GitHub PR descriptions and review comments into your decision history.

    \b
    Setup:
      keel github config --token ghp_xxx       # store your GitHub token
      keel github fetch                        # fetch PRs from current repo
      keel github fetch --repo owner/repo      # specific repo
      keel github fetch --process              # fetch and run processor immediately
    """
    if action == "config":
        if token:
            github_mod.set_token(token)
            rprint(f"[green]✓ GitHub token saved[/green]  ({token[:10]}...)")
        else:
            tok = github_mod.get_token()
            if tok:
                rprint(f"GitHub token: [green]set[/green]  ({tok[:10]}...)")
            else:
                rprint("[yellow]No GitHub token set.[/yellow]")
                rprint("  Run: [bold]keel github config --token ghp_...[/bold]")
                rprint("  Or set env: [dim]export GITHUB_TOKEN=ghp_...[/dim]")
        return

    if action == "detect":
        detected = github_mod.detect_repo()
        if detected:
            rprint(f"[green]Detected repo:[/green] {detected}")
        else:
            rprint("[yellow]Could not detect GitHub repo from git remote origin.[/yellow]")
            rprint("[dim]Make sure you're in a git repo with a GitHub remote.[/dim]")
        return

    # ── fetch ──
    target_repo = repo or github_mod.detect_repo()
    if not target_repo:
        rprint("[red]Could not detect repo. Use --repo owner/repo[/red]")
        raise typer.Exit(1)

    tok = token or github_mod.get_token()
    if not tok:
        rprint("[yellow]⚠ No GitHub token — requests may be rate-limited.[/yellow]")
        rprint("[dim]Set one with: keel github config --token ghp_...[/dim]")

    rprint(f"[bold]Fetching PRs[/bold] from [cyan]{target_repo}[/cyan]"
           f"  (last {since} days{f' · PR #{pr_number}' if pr_number else ''})")

    try:
        with console.status("Fetching from GitHub API..."):
            count = github_mod.fetch_and_queue(
                repo=target_repo, since_days=since,
                pr_number=pr_number, token=tok,
            )
    except RuntimeError as e:
        rprint(f"[red]GitHub API error:[/red] {e}")
        raise typer.Exit(1)

    if count == 0:
        rprint("[dim]No new PRs found (all already captured or no description).[/dim]")
        return

    rprint(f"[green]✓ {count} PR(s) queued[/green]")

    if process:
        rprint()
        proc.process_queue(verbose=True)
    else:
        rprint(f"[dim]Run [bold]keel process[/bold] to extract decisions from them.[/dim]")


# ─────────────────────────────────────────────
# Feature 10: Token cost visibility
# ─────────────────────────────────────────────

@app.command("cost")
def cost_cmd(
    since: int = typer.Option(30, "--since", "-d", help="Show usage from last N days"),
    breakdown: bool = typer.Option(False, "--breakdown", "-b", help="Show per-day breakdown"),
    reset: bool = typer.Option(False, "--reset", help="Clear the usage log"),
):
    """Show how much keel's LLM calls are costing you.

    \b
    keel cost              # last 30 days summary
    keel cost --since 7    # last 7 days
    keel cost --breakdown  # per-day spending chart
    """
    if reset:
        if cost_mod.USAGE_LOG.exists():
            typer.confirm("Clear the entire usage log?", abort=True)
            cost_mod.USAGE_LOG.unlink()
            rprint("[green]✓ Usage log cleared[/green]")
        else:
            rprint("[dim]No usage log to clear.[/dim]")
        return

    data = cost_mod.get_summary(since_days=since)

    if not data["records"]:
        rprint(f"[dim]No usage recorded in the last {since} days.[/dim]")
        rprint("[dim](Usage is logged automatically after keel makes LLM calls)[/dim]")
        return

    # ── Summary ──
    rprint(f"\n[bold]LLM cost[/bold]  [dim]last {since} days[/dim]\n")

    stat_table = Table(show_header=False, box=None, padding=(0, 2))
    stat_table.add_column(style="dim", width=20)
    stat_table.add_column(style="bold")
    stat_table.add_row("Total calls",    str(len(data["records"])))
    stat_table.add_row("Input tokens",   f"{data['total_input']:,}")
    stat_table.add_row("Output tokens",  f"{data['total_output']:,}")
    total_cost = data["total_cost"]
    cost_color = "green" if total_cost < 0.50 else ("yellow" if total_cost < 2.0 else "red")
    stat_table.add_row("Estimated cost", f"[{cost_color}]${total_cost:.4f}[/{cost_color}]")
    console.print(stat_table)

    # ── Per-model breakdown ──
    if data["by_model"]:
        rprint("\n[bold]By model[/bold]")
        model_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        model_table.add_column("Model")
        model_table.add_column("Calls",  justify="right", width=8)
        model_table.add_column("Input",  justify="right", width=12)
        model_table.add_column("Output", justify="right", width=12)
        model_table.add_column("Cost",   justify="right", width=10)
        for model, v in sorted(data["by_model"].items(),
                               key=lambda x: x[1]["cost"], reverse=True):
            model_table.add_row(
                model,
                str(v["calls"]),
                f"{v['input']:,}",
                f"{v['output']:,}",
                f"${v['cost']:.4f}",
            )
        console.print(model_table)

    # ── Per-day chart ──
    if breakdown and data["by_day"]:
        rprint("\n[bold]Daily spend[/bold]")
        max_cost = max(v["cost"] for v in data["by_day"].values()) or 0.001
        for day, v in data["by_day"].items():
            bar_len = int((v["cost"] / max_cost) * 30)
            bar = "█" * bar_len
            cost_color = "green" if v["cost"] < 0.05 else ("yellow" if v["cost"] < 0.20 else "red")
            rprint(f"  [dim]{day}[/dim]  [{cost_color}]{bar}[/{cost_color}]  "
                   f"[dim]${v['cost']:.4f}  {v['calls']} calls[/dim]")


# ─────────────────────────────────────────────
# Feature 11: Decision quality correlation
# ─────────────────────────────────────────────

@app.command("quality")
def quality_cmd(
    decision_id: Optional[str] = typer.Argument(None,
                                                  help="Rate the outcome quality of a specific decision"),
    rating: Optional[str] = typer.Option(None, "--rating", "-r",
                                          help="good | neutral | bad"),
    stats: bool = typer.Option(False, "--stats", "-s",
                               help="Show principle quality correlation table"),
    narrative: bool = typer.Option(False, "--narrative", "-n",
                                    help="LLM analysis of which principles produce good outcomes"),
):
    """Correlate your principles with decision outcomes.

    \b
    Workflow:
      keel outcome <id> --text "..."          # record what happened
      keel quality <id> --rating good        # rate the outcome quality
      keel quality --stats                   # see which principles correlate with good outcomes
      keel quality --narrative               # LLM analysis
    """
    from rich.markdown import Markdown

    # ── Rate a specific decision ──
    if decision_id:
        d = store.get_by_id(decision_id)
        if not d:
            rprint(f"[red]Decision {decision_id} not found.[/red]")
            raise typer.Exit(1)

        if not d.outcome:
            rprint(f"[yellow]No outcome recorded for [{decision_id}].[/yellow]")
            rprint(f"  First record the outcome: [bold]keel outcome {decision_id} --text \"..\"[/bold]")
            raise typer.Exit(1)

        valid = quality_mod.VALID_QUALITIES
        if not rating:
            rprint(f"\n[bold]{d.title}[/bold]  [{decision_id}]")
            rprint(f"[dim]Outcome: {d.outcome[:120]}[/dim]\n")
            rating = typer.prompt(
                f"  Rate this outcome [{'/'.join(valid)}]",
                prompt_suffix=" → ",
            ).strip().lower()

        if rating not in valid:
            rprint(f"[red]Rating must be one of: {', '.join(valid)}[/red]")
            raise typer.Exit(1)

        store.update_outcome_quality(decision_id, rating)
        color = "green" if rating == "good" else ("red" if rating == "bad" else "yellow")
        rprint(f"[{color}]✓ [{decision_id}] rated as {rating}[/{color}]")
        rprint("[dim]keel quality --stats to see how this affects your principle correlations.[/dim]")
        return

    # ── Stats table ──
    if stats or (not narrative):
        decisions = store.get_with_outcomes()
        if not decisions:
            rprint("[dim]No rated outcomes yet.[/dim]")
            rprint("  1. Record an outcome: [bold]keel outcome <id> --text \"..\"[/bold]")
            rprint("  2. Rate it:           [bold]keel quality <id> --rating good[/bold]")
            raise typer.Exit(0)

        qs = quality_mod.quick_stats(decisions)
        rprint(f"\n[bold]Outcome quality[/bold]  [dim]{qs['total']} rated[/dim]\n")

        overview = Table(show_header=False, box=None, padding=(0, 2))
        overview.add_column(style="dim", width=18)
        overview.add_column(style="bold")
        overview.add_row("Good outcomes",    f"[green]{qs['good']}[/green]")
        overview.add_row("Neutral outcomes", f"[dim]{qs['neutral']}[/dim]")
        overview.add_row("Bad outcomes",     f"[red]{qs['bad']}[/red]")
        if qs["rate"] is not None:
            rate_color = "green" if qs["rate"] >= 0.6 else ("yellow" if qs["rate"] >= 0.4 else "red")
            overview.add_row("Good rate", f"[{rate_color}]{qs['rate']:.0%}[/{rate_color}]")
        console.print(overview)

        principle_stats = quality_mod.get_principle_stats()
        if principle_stats:
            rprint("\n[bold]Principle quality correlation[/bold]"
                   "  [dim](principles ranked by frequency in outcomes)[/dim]\n")
            p_table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
            p_table.add_column("Principle")
            p_table.add_column("Good",    justify="right", width=6)
            p_table.add_column("Neutral", justify="right", width=8)
            p_table.add_column("Bad",     justify="right", width=6)
            p_table.add_column("Signal",  width=14)
            for principle, v in list(principle_stats.items())[:15]:
                total = v["total"]
                if total == 0:
                    continue
                good_rate = v["good"] / total
                signal_color = "green" if good_rate >= 0.6 else ("red" if good_rate < 0.3 else "yellow")
                signal = "reliable" if good_rate >= 0.6 else ("risky" if good_rate < 0.3 else "mixed")
                p_table.add_row(
                    principle[:55],
                    f"[green]{v['good']}[/green]",
                    f"[dim]{v['neutral']}[/dim]",
                    f"[red]{v['bad']}[/red]",
                    f"[{signal_color}]{signal}[/{signal_color}]",
                )
            console.print(p_table)

    if narrative:
        rprint()
        with console.status("Analyzing outcome patterns..."):
            report = quality_mod.generate_quality_report()
        if report is None:
            rprint("[yellow]Need at least 3 rated outcomes for analysis.[/yellow]")
            raise typer.Exit(0)
        console.print(Panel(
            Markdown(report),
            title="[bold]Principle Quality Analysis[/bold]",
            border_style="green",
        ))
    elif not decision_id and not stats:
        rprint(f"\n[dim]Add --narrative for LLM analysis of your principle patterns.[/dim]")


# ─────────────────────────────────────────────
# Feature 12: Team mode
# ─────────────────────────────────────────────

@app.command("team")
def team_cmd(
    action: str = typer.Argument("list",
                                  help="Action: list | export | add | remove | conflicts | persona"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Team member name"),
    file: Optional[str] = typer.Option(None, "--file", "-f",
                                        help="Path to exported decisions JSON"),
    output: Optional[str] = typer.Option(None, "--output", "-o",
                                          help="Output file for export (default: stdout)"),
    limit: int = typer.Option(0, "--limit", help="Max decisions to export (0 = all)"),
):
    """Share decisions with teammates and detect principle conflicts.

    \b
    Workflow:
      keel team export --output my_decisions.json    # export your decisions
      # share the file with a teammate
      keel team add --name alice --file alice.json   # import their decisions
      keel team conflicts --name alice               # see where you disagree
      keel team persona                              # build a shared team philosophy

    \b
    Actions:
      list        List imported team members
      export      Export your decisions to JSON
      add         Import a teammate's decision export
      remove      Remove a team member's data
      conflicts   LLM analysis of principle conflicts with a member
      persona     Generate a shared team engineering philosophy
    """
    from rich.markdown import Markdown

    # ── list ──
    if action == "list":
        members = team_mod.list_members()
        if not members:
            rprint("[dim]No team members yet.[/dim]")
            rprint("  Export yours:   [bold]keel team export --output mine.json[/bold]")
            rprint("  Add a member:   [bold]keel team add --name alice --file alice.json[/bold]")
            return
        rprint(f"\n[bold]Team members[/bold]  [dim]{len(members)} imported[/dim]\n")
        table = Table(show_header=True, header_style="bold", box=None, padding=(0, 2))
        table.add_column("Name",       width=20)
        table.add_column("Decisions",  justify="right", width=12)
        table.add_column("Imported",   width=14)
        for m in members:
            table.add_row(m["name"], str(m["count"]), m["imported_at"])
        console.print(table)
        rprint(f"\n[dim]keel team conflicts --name <member>   to see where you disagree[/dim]")
        return

    # ── export ──
    if action == "export":
        with console.status("Exporting decisions..."):
            data = team_mod.export_decisions(limit=limit)
        if output:
            from pathlib import Path as _Path
            _Path(output).write_text(data)
            decisions = store.get_all()
            count = len(decisions[:limit]) if limit else len(decisions)
            rprint(f"[green]✓ {count} decisions exported → {output}[/green]")
            rprint("[dim]Share this file with your teammate. They run:[/dim]")
            rprint(f"[dim]  keel team add --name yourname --file {output}[/dim]")
        else:
            rprint(data)
        return

    # ── add ──
    if action == "add":
        if not name:
            rprint("[red]--name required for add[/red]")
            raise typer.Exit(1)
        if not file:
            rprint("[red]--file required for add[/red]")
            raise typer.Exit(1)
        count = team_mod.import_member(name, file)
        rprint(f"[green]✓ Imported {count} decisions from {name}[/green]")
        rprint(f"[dim]keel team conflicts --name {name}   to see conflicts[/dim]")
        return

    # ── remove ──
    if action == "remove":
        if not name:
            rprint("[red]--name required for remove[/red]")
            raise typer.Exit(1)
        if team_mod.remove_member(name):
            rprint(f"[green]✓ Removed {name}[/green]")
        else:
            rprint(f"[red]Member '{name}' not found.[/red]")
        return

    # ── conflicts ──
    if action == "conflicts":
        if not name:
            rprint("[red]--name required for conflicts[/red]")
            raise typer.Exit(1)
        with console.status(f"Comparing your principles with {name}'s..."):
            result = team_mod.find_conflicts(name)
        if result is None:
            rprint(f"[yellow]No data for '{name}'. Did you run: keel team add --name {name}?[/yellow]")
            raise typer.Exit(1)
        console.print(Panel(
            Markdown(result),
            title=f"[bold]Principle conflicts: you vs {name}[/bold]",
            border_style="red",
        ))
        return

    # ── persona ──
    if action == "persona":
        members = team_mod.list_members()
        if not members:
            rprint("[yellow]No team members imported yet.[/yellow]")
            rprint("  Add one with: [bold]keel team add --name alice --file alice.json[/bold]")
            raise typer.Exit(1)
        rprint(f"[bold]Building team persona[/bold]  "
               f"[dim]{len(members)} member(s) + you[/dim]")
        with console.status("Synthesizing team philosophy..."):
            result = team_mod.build_team_persona()
        if result is None:
            rprint("[yellow]Not enough data to build team persona.[/yellow]")
            raise typer.Exit(0)
        console.print(Panel(
            Markdown(result),
            title="[bold]Team Engineering Philosophy[/bold]",
            border_style="cyan",
        ))
        return

    rprint(f"[red]Unknown action: {action}[/red]")
    rprint("Valid: list | export | add | remove | conflicts | persona")
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
