"""Final report construction and Markdown rendering."""

from __future__ import annotations

from guided_reflection_cli.llm import ReflectionLLM
from guided_reflection_cli.schemas import (
    AgendaCompletion,
    FinalReport,
    QuestionCompletion,
    RequiredQuestionStatus,
    RubricScore,
    SessionState,
)


def build_final_report(state: SessionState, llm: ReflectionLLM) -> FinalReport:
    narrative = llm.generate_narrative(state)
    agenda_completion_report = [
        AgendaCompletion(
            atom_id=atom.id,
            description=atom.description,
            status=state.agenda_atom_statuses.get(atom.id),
            evidence=state.agenda_atom_evidence.get(atom.id, []),
        )
        for atom in state.template.agenda_atoms
    ]
    required_question_report = [
        QuestionCompletion(
            question_id=question.id,
            prompt=question.prompt,
            status=state.required_question_statuses.get(question.id, RequiredQuestionStatus.UNASKED),
            attempts=state.question_attempt_counts.get(question.id, 0),
        )
        for question in state.template.question_bank
        if question.required
    ]
    rubric_scores = [
        RubricScore(
            rubric_id=criterion.id,
            description=criterion.description,
            score=state.rubric_progress.get(criterion.id, criterion.scale_min),
            max_score=criterion.scale_max,
        )
        for criterion in state.template.rubric
    ]

    teacher_notes = [*narrative.teacher_notes]
    met_atoms = [item.description for item in agenda_completion_report if item.status.value == "met"]
    unmet_atoms = [item.description for item in agenda_completion_report if item.status.value != "met"]
    if met_atoms:
        teacher_notes.append(f"Strengths shown: {met_atoms[0]}.")
    if unmet_atoms:
        teacher_notes.append(f"Follow-up needed on: {unmet_atoms[0]}.")
    if state.open_issues:
        teacher_notes.append(f"Open issues: {', '.join(state.open_issues[:3])}.")

    return FinalReport(
        final_student_reflection=narrative.final_student_reflection,
        agenda_completion_report=agenda_completion_report,
        required_question_report=required_question_report,
        rubric_scores=rubric_scores,
        teacher_notes=teacher_notes,
        session_summary=narrative.session_summary,
        stop_reason=state.stop_reason,
    )


def render_markdown_report(state: SessionState, report: FinalReport) -> str:
    agenda_rows = "\n".join(
        f"| {item.atom_id} | {item.status.value} | {item.description} | {'; '.join(item.evidence) or '-'} |"
        for item in report.agenda_completion_report
    )
    question_rows = "\n".join(
        f"| {item.question_id} | {item.status.value} | {item.attempts} | {item.prompt} |"
        for item in report.required_question_report
    )
    rubric_rows = "\n".join(
        f"| {item.rubric_id} | {item.score}/{item.max_score} | {item.description} |"
        for item in report.rubric_scores
    )
    teacher_notes = "\n".join(f"- {note}" for note in report.teacher_notes) or "- None"
    return f"""# Guided Reflection Report

## Session Info

- Session ID: {state.session_id}
- Template ID: {state.template.template_id}
- Student ID: {state.student_profile.student_id}
- Stop reason: {report.stop_reason.value}

## Session Summary

{report.session_summary}

## Final Student Reflection

{report.final_student_reflection}

## Agenda Completion

| Atom ID | Status | Description | Evidence |
| --- | --- | --- | --- |
{agenda_rows}

## Required Questions

| Question ID | Status | Attempts | Prompt |
| --- | --- | --- | --- |
{question_rows}

## Rubric Summary

| Rubric ID | Score | Description |
| --- | --- | --- |
{rubric_rows}

## Teacher Notes

{teacher_notes}
"""


def render_transcript_markdown(state: SessionState) -> str:
    lines = ["# Transcript", ""]
    for index, turn in enumerate(state.transcript, start=1):
        label = turn.speaker.upper()
        question_suffix = f" [{turn.question_id}]" if turn.question_id else ""
        lines.append(f"{index}. {label}{question_suffix}")
        lines.append("")
        lines.append(turn.text)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
