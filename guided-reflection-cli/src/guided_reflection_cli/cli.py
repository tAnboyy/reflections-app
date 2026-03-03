"""Typer CLI entrypoint for guided reflection sessions."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from guided_reflection_cli.session_runner import run_interactive_session
from guided_reflection_cli.template_loader import validate_template, write_starter_template


app = typer.Typer(help="Guided reflection CLI.")
template_app = typer.Typer(help="Template utilities.")
app.add_typer(template_app, name="template")

console = Console()


@template_app.command("init")
def template_init(output_path: Path) -> None:
    """Write a starter template YAML file."""
    created = write_starter_template(output_path)
    console.print(f"[green]Starter template written to[/green] {created}")


@template_app.command("validate")
def template_validate(template_path: Path) -> None:
    """Validate a reflection template YAML file."""
    is_valid, message = validate_template(template_path)
    if not is_valid:
        console.print(f"[red]{message}[/red]")
        raise typer.Exit(code=1)
    console.print(f"[green]{message}[/green]")


@app.command("run")
def run(
    template: Path = typer.Option(..., exists=True, readable=True, help="Path to the template YAML."),
    student: Path = typer.Option(..., exists=True, readable=True, help="Path to the student YAML."),
    output_dir: Path | None = typer.Option(None, help="Optional output directory for artifacts."),
    max_questions: int | None = typer.Option(
        None,
        min=1,
        help="Override the template max_questions cap for assistant questions.",
    ),
    max_turns: int | None = typer.Option(None, min=1, help="Override the template max_turns."),
    debug: bool = typer.Option(False, help="Print planner and issue debug output."),
) -> None:
    """Run an interactive guided reflection session."""
    try:
        run_interactive_session(
            template_path=template,
            student_path=student,
            output_dir=output_dir,
            max_questions=max_questions,
            max_turns=max_turns,
            debug=debug,
            console=console,
        )
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


if __name__ == "__main__":
    app()
