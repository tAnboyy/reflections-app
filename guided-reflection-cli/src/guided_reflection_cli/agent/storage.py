"""Persistence helpers for runs and transcripts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from guided_reflection_cli.agent.memory import RUNS_ROOT, append_notes, load_history, save_history
from guided_reflection_cli.agent.state import AgendaStatus, SessionState


def timestamp_slug() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace(":", "-").replace("+00:00", "Z")


def create_run_dir(template_id: str, student_id: str, output_root: Path | None = None) -> Path:
    root = output_root or RUNS_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{timestamp_slug()}_{template_id}_{student_id}"


def render_transcript_md(state: SessionState) -> str:
    lines = ["# Transcript", ""]
    for idx, turn in enumerate(state.transcript, start=1):
        label = turn.speaker.upper()
        suffix = f" [{turn.question_id}]" if turn.question_id else ""
        lines.append(f"{idx}. {label}{suffix}")
        lines.append("")
        lines.append(turn.text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_report_md(state: SessionState) -> str:
    agenda_lines = []
    for atom in state.agenda.agenda_atoms:
        status = state.agenda_statuses.get(atom.id, AgendaStatus.UNKNOWN).value
        agenda_lines.append(
            f"- {atom.id} ({'required' if atom.required else 'optional'}): {status} -- {atom.description}"
        )

    teacher_notes = []
    if state.summary:
        teacher_notes.extend(state.summary.get("teacher_notes", []))

    lines = [
        "# Guided Reflection Report",
        "",
        f"- Session ID: {state.session_id}",
        f"- Topic: {state.agenda.topic}",
        f"- Student: {state.student.display_name}",
        f"- Stop reason: {state.stop_reason.value if state.stop_reason else 'incomplete'}",
        "",
        "## Agenda Status",
        *agenda_lines,
        "",
        "## Summary",
        state.summary.get("session_summary", "") if state.summary else "",
        "",
        "## Teacher Notes",
    ]
    if teacher_notes:
        lines.extend(f"- {note}" for note in teacher_notes)
    else:
        lines.append("- None")
    return "\n".join(lines)


def persist_run(state: SessionState) -> Path:
    if state.output_dir is None:
        state.output_dir = create_run_dir(state.agenda.template_id, state.student.student_id)
    state.output_dir.mkdir(parents=True, exist_ok=True)
    (state.output_dir / "state.json").write_text(
        json.dumps(state.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    (state.output_dir / "transcript.md").write_text(render_transcript_md(state), encoding="utf-8")
    (state.output_dir / "report.md").write_text(render_report_md(state), encoding="utf-8")
    if state.summary and state.summary.get("notes_append"):
        append_notes(state.student.student_id, state.summary["notes_append"])
    history = load_history(state.student.student_id)
    history.append(
        {
            "run_id": state.output_dir.name,
            "template_id": state.agenda.template_id,
            "summary": state.summary.get("session_summary", "") if state.summary else "",
            "report_path": str(state.output_dir / "report.md"),
            "transcript_path": str(state.output_dir / "transcript.md"),
            "timestamp": timestamp_slug(),
        }
    )
    save_history(state.student.student_id, history)
    return state.output_dir
