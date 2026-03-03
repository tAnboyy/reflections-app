"""Typer entrypoint for the lean agent CLI."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console
from dotenv import load_dotenv, find_dotenv

from guided_reflection_cli.agent.graph import run_session
from guided_reflection_cli.agent.memory import ensure_roots

app = typer.Typer(help="LangGraph-based guided reflection agent.")
console = Console()


@app.command("run")
def run(
    agenda: Path | None = typer.Option(
        None,
        exists=True,
        readable=True,
        help="Path to agenda file. If plain text, it becomes the single agenda focus. If YAML, parsed as before.",
    ),
    agenda_text: str = typer.Option(
        None,
        help="Inline agenda paragraph (alternative to --agenda).",
    ),
    student_id: str = typer.Option(..., help="Student ID (required)."),
    profile: Path | None = typer.Option(
        None,
        exists=True,
        readable=True,
        help="Path to student profile YAML (optional; defaults to empty profile).",
    ),
    submissions: list[Path] = typer.Option(
        None,
        help="Paths to recent submissions (.txt/.md/.json).",
    ),
    max_turns: int | None = typer.Option(None, min=1, help="Max student turns."),
    model: str = typer.Option(
        lambda: os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        help="OpenAI chat model (default: env OPENAI_MODEL or gpt-4o-mini).",
    ),
    output_dir: Path | None = typer.Option(None, help="Optional directory for run artifacts."),
) -> None:
    """Run an interactive guided reflection session."""
    # Load nearest .env (working dir first), then fallback to default search
    env_path = find_dotenv(usecwd=True)
    if env_path:
        load_dotenv(dotenv_path=env_path, override=True)
    else:
        load_dotenv(override=True)
    ensure_roots()
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        console.print("[red]OPENAI_API_KEY is required.[/red]")
        raise typer.Exit(code=1)
    if not agenda and not agenda_text:
        console.print("[red]Provide either --agenda or --agenda-text.[/red]")
        raise typer.Exit(code=1)
    if agenda and agenda_text:
        console.print("[red]Choose only one of --agenda or --agenda-text.[/red]")
        raise typer.Exit(code=1)
    session = run_session(
        agenda_path=agenda,
        agenda_text=agenda_text,
        student_id=student_id,
        profile_path=profile,
        submissions=submissions or [],
        max_turns=max_turns,
        model_name=model,
        output_dir=output_dir,
        console=console,
    )
    if session.stop_reason is None:
        console.print("[yellow]Session ended without a stop reason.[/yellow]")


if __name__ == "__main__":
    app()
