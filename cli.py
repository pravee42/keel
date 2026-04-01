#!/usr/bin/env python3
"""decide — git diff for your thinking."""

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

    rprint(f"\n[green]Done.[/green] Queue: [dim]{proc.QUEUE_PATH}[/dim]")
    rprint("Run [bold]decide process[/bold] to process captured events manually.")


@app.command()
def process(
    quiet: bool = typer.Option(False, "--quiet", "-q"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max events to process"),
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
    save: bool = typer.Option(True, "--save/--no-save", help="Save digest to ~/.decisions/digests/"),
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
        digest_dir = Path.home() / ".decisions" / "digests"
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

    digest_dir = Path.home() / ".decisions" / "digests"
    if not digest_dir.exists() or not list(digest_dir.glob("*.json")):
        rprint("[dim]No digests yet. Run: decide weekly[/dim]")
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
    rprint(f"\n[dim]Run [bold]decide weekly[/bold] to generate a new one.[/dim]")


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
            rprint(f"  Run: [bold]decide config key {name} <your-key>[/bold]")
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


if __name__ == "__main__":
    app()
