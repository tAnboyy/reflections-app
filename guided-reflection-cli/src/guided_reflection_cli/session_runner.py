"""Interactive CLI session runner."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from rich.console import Console

from guided_reflection_cli.graph import GuidedReflectionGraph
from guided_reflection_cli.llm import build_llm_client
from guided_reflection_cli.memory import NullMemoryProvider
from guided_reflection_cli.schemas import SessionState, StopReason
from guided_reflection_cli.settings import Settings
from guided_reflection_cli.storage import persist_session_artifacts
from guided_reflection_cli.template_loader import load_student_profile, load_template


def run_interactive_session(
    template_path: str | Path,
    student_path: str | Path,
    output_dir: str | Path | None = None,
    max_turns: int | None = None,
    debug: bool = False,
    console: Console | None = None,
    input_func: Callable[[str], str] | None = None,
) -> tuple[Path, SessionState]:
    console = console or Console()
    input_func = input_func or input

    template = load_template(template_path)
    student = load_student_profile(student_path)
    llm = build_llm_client(Settings.from_env())
    graph = GuidedReflectionGraph(llm=llm, memory_provider=NullMemoryProvider())
    state = graph.initialize_session(template, student, max_turns_override=max_turns)

    console.print(f"[bold]Topic:[/bold] {state.template.title}")
    console.print(f"[bold]Student:[/bold] {state.student_profile.display_name}")

    while True:
        if state.stop_reason is not None and state.final_report is None:
            state = graph.step(state)
        elif state.stop_reason is not None and state.final_report is not None:
            break
        else:
            state = graph.step(state)

        if state.stop_reason is not None and state.final_report is not None:
            break

        if state.last_assistant_question is None:
            state.stop_reason = StopReason.EVALUATION_ERROR
            continue

        console.print(f"[cyan]Tutor:[/cyan] {state.last_assistant_question.question_text}")
        if debug and state.last_plan is not None:
            console.print(
                f"[dim]Plan: {state.last_plan.strategy.value} | "
                f"targets={state.last_plan.target_atom_ids} | "
                f"{state.last_plan.reasoning_summary}[/dim]"
            )

        try:
            student_reply = input_func("Student> ")
        except EOFError:
            state.stop_reason = StopReason.STUDENT_EXIT
            continue
        except KeyboardInterrupt:
            state.stop_reason = StopReason.INTERRUPT
            console.print("\n[yellow]Interrupted. Finalizing partial session...[/yellow]")
            continue

        if student_reply.strip().lower() in {"exit", "quit"}:
            state.stop_reason = StopReason.STUDENT_EXIT
            continue

        state.pending_student_reply = student_reply
        state = graph.step(state)
        if debug and state.open_issues:
            console.print(f"[dim]Open issues: {state.open_issues}[/dim]")

    run_dir = persist_session_artifacts(state, output_dir=output_dir)
    console.print(f"[green]Saved artifacts:[/green] {run_dir}")
    console.print(f"[bold]Stop reason:[/bold] {state.stop_reason.value}")
    return run_dir, state
