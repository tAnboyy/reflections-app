"""File-backed persistence for run artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from guided_reflection_cli.reporting import render_markdown_report, render_transcript_markdown
from guided_reflection_cli.schemas import SessionState
from guided_reflection_cli.utils import ensure_directory, project_root, slugify, utc_timestamp


def default_runs_dir() -> Path:
    return project_root() / "runs"


def create_run_directory(state: SessionState, output_dir: str | Path | None = None) -> Path:
    root = Path(output_dir) if output_dir else default_runs_dir()
    timestamp = utc_timestamp().replace(":", "-")
    run_dir_name = (
        f"{timestamp}_{slugify(state.template.template_id)}_{slugify(state.student_profile.student_id)}"
    )
    return ensure_directory(root / run_dir_name)


def persist_session_artifacts(state: SessionState, output_dir: str | Path | None = None) -> Path:
    if state.final_report is None:
        raise ValueError("Cannot persist a session before final_report has been created.")
    run_dir = create_run_directory(state, output_dir=output_dir)
    result_payload = {
        "session_id": state.session_id,
        "template": {
            "template_id": state.template.template_id,
            "version": state.template.version,
            "title": state.template.title,
            "topic": state.template.topic,
        },
        "student": {
            "student_id": state.student_profile.student_id,
            "display_name": state.student_profile.display_name,
            "course": state.student_profile.course,
        },
        "stop_reason": state.stop_reason.value if state.stop_reason else None,
        "conversation_phase": state.conversation_phase.value,
        "turn_index": state.turn_index,
        "asked_question_ids": state.asked_question_ids,
        "required_question_statuses": {
            key: value.value for key, value in state.required_question_statuses.items()
        },
        "agenda_atom_statuses": {
            key: value.value for key, value in state.agenda_atom_statuses.items()
        },
        "agenda_atom_evidence": state.agenda_atom_evidence,
        "rubric_progress": state.rubric_progress,
        "open_issues": state.open_issues,
        "transcript": [turn.model_dump(mode="json") for turn in state.transcript],
        "final_report": state.final_report.model_dump(mode="json"),
        "debug_trace": state.debug_trace,
    }
    (run_dir / "result.json").write_text(
        json.dumps(result_payload, indent=2),
        encoding="utf-8",
    )
    (run_dir / "report.md").write_text(
        render_markdown_report(state, state.final_report),
        encoding="utf-8",
    )
    (run_dir / "transcript.md").write_text(
        render_transcript_markdown(state),
        encoding="utf-8",
    )
    return run_dir
