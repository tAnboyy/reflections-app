"""Prompt builders for live model-backed question phrasing and summaries."""

from __future__ import annotations

from textwrap import dedent

from guided_reflection_cli.schemas import QuestionPlan, ReflectionTemplate, SessionState, StudentProfile


def build_planner_prompt(state: SessionState) -> str:
    remaining_atoms = [
        atom.id
        for atom in state.template.agenda_atoms
        if atom.required and state.agenda_atom_statuses.get(atom.id) != "met"
    ]
    remaining_questions = [
        question.id
        for question in state.template.question_bank
        if question.required and state.required_question_statuses.get(question.id) != "acceptable"
    ]
    return dedent(
        f"""
        You are planning the next move in a guided student reflection.
        Topic: {state.template.topic}
        Remaining required atoms: {remaining_atoms}
        Remaining required questions: {remaining_questions}
        Current phase: {state.conversation_phase.value}
        Keep the next move focused and agenda-driven.
        """
    ).strip()


def build_question_generation_messages(
    template: ReflectionTemplate,
    student_profile: StudentProfile,
    plan: QuestionPlan,
    base_prompt: str,
    transcript_excerpt: str,
) -> list[dict[str, str]]:
    system = dedent(
        """
        You are a guided reflection tutor.
        Ask exactly one concise question.
        Keep the educator agenda primary.
        Do not reveal internal planning or grading.
        """
    ).strip()
    user = dedent(
        f"""
        Topic: {template.topic}
        Assignment statement: {template.assignment.statement}
        Student: {student_profile.display_name}
        Standing summary: {student_profile.standing_summary or "Not provided"}
        Strengths: {", ".join(student_profile.strengths) or "Not provided"}
        Growth areas: {", ".join(student_profile.growth_areas) or "Not provided"}
        Preferred tone: {student_profile.preferences.get("tone", template.policies.tone)}
        Strategy: {plan.strategy.value}
        Phase: {plan.phase.value}
        Base educator question: {base_prompt}
        Recent transcript:
        {transcript_excerpt or "(none yet)"}

        Rephrase the question so it is personalized, concise, and still clearly targets the same requirement.
        """
    ).strip()
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def build_turn_evaluator_prompt(state: SessionState, student_reply: str) -> str:
    question = state.last_assistant_question.question_text if state.last_assistant_question else ""
    return dedent(
        f"""
        Evaluate the latest student reply for a guided reflection.
        Question asked: {question}
        Student reply: {student_reply}
        Keep the agenda and required completion criteria dominant.
        """
    ).strip()


def build_final_report_messages(state: SessionState) -> list[dict[str, str]]:
    transcript = "\n".join(f"{turn.speaker}: {turn.text}" for turn in state.transcript)
    system = "You produce concise educational summaries and teacher notes."
    user = dedent(
        f"""
        Topic: {state.template.topic}
        Assignment: {state.template.assignment.statement}
        Stop reason: {state.stop_reason.value if state.stop_reason else "unknown"}
        Transcript:
        {transcript}

        Write a concise student reflection summary and a brief session summary.
        """
    ).strip()
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]
