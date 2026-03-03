"""Deterministic planning and evaluation logic for guided reflections."""

from __future__ import annotations

import re
from textwrap import shorten

from guided_reflection_cli.schemas import (
    AgendaAtom,
    AgendaAtomUpdate,
    AgendaStatus,
    AnswerAcceptability,
    ConversationPhase,
    PromptSource,
    QuestionPlan,
    QuestionSpec,
    ReflectionTemplate,
    RequiredQuestionStatus,
    RubricCriterion,
    RubricObservation,
    SessionState,
    Strategy,
    TurnEvaluation,
    TurnPurpose,
    TurnRecord,
)
from guided_reflection_cli.utils import agenda_focus, contains_any, count_words, unique_preserving_order


POSITION_HINTS = [
    "i think",
    "i believe",
    "in my view",
    "my position",
    "i would",
    "should",
    "must",
    "i argue",
]
EXAMPLE_HINTS = [
    "for example",
    "for instance",
    "when i",
    "during",
    "in class",
    "at work",
    "in my project",
    "last semester",
    "once",
]
COUNTERARGUMENT_HINTS = [
    "however",
    "although",
    "on the other hand",
    "some might say",
    "at the same time",
    "while",
]
NEXT_ACTION_HINTS = [
    "next time",
    "i will",
    "i plan",
    "going forward",
    "my next step",
]
UNCERTAINTY_HINTS = ["i don't know", "not sure", "confused", "unclear", "maybe"]
STOP_INTENT_PHRASES = [
    "please stop",
    "can we stop",
    "lets stop",
    "stop asking",
    "no more questions",
    "please end",
    "can we end",
    "lets end",
    "end this",
    "wrap this up",
    "finish this",
    "i want to stop",
    "i want to end",
    "im done",
    "this is enough",
    "thats enough",
    "done with the questions",
    "done with this reflection",
]


def initialize_state_maps(template: ReflectionTemplate) -> tuple[
    dict[str, RequiredQuestionStatus],
    dict[str, int],
    dict[str, int],
    dict[str, AgendaStatus],
    dict[str, list[str]],
    dict[str, int],
    dict[str, int],
    dict[str, int],
    dict[str, list[str]],
]:
    required_question_statuses = {
        question.id: RequiredQuestionStatus.UNASKED
        for question in template.question_bank
        if question.required
    }
    question_attempt_counts = {question.id: 0 for question in template.question_bank if question.required}
    question_unacceptable_counts = {
        question.id: 0 for question in template.question_bank if question.required
    }
    agenda_atom_statuses = {atom.id: AgendaStatus.UNKNOWN for atom in template.agenda_atoms}
    agenda_atom_evidence = {atom.id: [] for atom in template.agenda_atoms}
    rubric_progress = {criterion.id: criterion.scale_min for criterion in template.rubric}
    agenda_atom_attempt_counts = {atom.id: 0 for atom in template.agenda_atoms}
    agenda_atom_last_asked_turn = {atom.id: 0 for atom in template.agenda_atoms}
    agenda_atom_missing = {atom.id: [] for atom in template.agenda_atoms}
    return (
        required_question_statuses,
        question_attempt_counts,
        question_unacceptable_counts,
        agenda_atom_statuses,
        agenda_atom_evidence,
        rubric_progress,
        agenda_atom_attempt_counts,
        agenda_atom_last_asked_turn,
        agenda_atom_missing,
    )


def student_reply_signals_exit(reply: str) -> bool:
    normalized = re.sub(r"[^a-z0-9\s]", "", reply.lower())
    if not normalized:
        return False
    if normalized in {"exit", "quit"}:
        return True
    word_count = len(normalized.split())
    if word_count > 12:
        return False
    return any(phrase in normalized for phrase in STOP_INTENT_PHRASES)


def determine_phase(state: SessionState) -> ConversationPhase:
    if state.template.uses_agenda_first():
        required_atoms = [atom for atom in state.template.agenda_atoms if atom.required]
        if state.turn_index == 0:
            return ConversationPhase.WARMUP
        if required_atoms and all(state.agenda_atom_attempt_counts.get(atom.id, 0) >= 1 for atom in required_atoms):
            return ConversationPhase.SYNTHESIS
        return ConversationPhase.PROBING

    unmet_required_atoms = [
        atom.id
        for atom in state.template.agenda_atoms
        if atom.required and state.agenda_atom_statuses.get(atom.id) != AgendaStatus.MET
    ]
    remaining_required_questions = [
        question.id
        for question in state.template.question_bank
        if question.required
        and state.required_question_statuses.get(question.id) != RequiredQuestionStatus.ACCEPTABLE
    ]
    remaining_total = len(unmet_required_atoms) + len(remaining_required_questions)
    if state.turn_index == 0:
        return ConversationPhase.WARMUP
    if remaining_total <= 1:
        return ConversationPhase.SYNTHESIS
    return ConversationPhase.PROBING


def plan_next_step(state: SessionState) -> QuestionPlan:
    if state.template.uses_agenda_first():
        return plan_next_agenda_step(state)
    return plan_next_legacy_step(state)


def plan_next_agenda_step(state: SessionState) -> QuestionPlan:
    phase = determine_phase(state)
    for atom in state.template.agenda_atoms:
        if not atom.required:
            continue
        if state.agenda_atom_attempt_counts.get(atom.id, 0) >= 1:
            continue
        strategy = Strategy.CLARIFY if phase == ConversationPhase.WARMUP else Strategy.PROBE
        return QuestionPlan(
            strategy=strategy,
            target_atom_ids=[atom.id],
            phase=phase,
            reasoning_summary=f"Ask agenda atom '{atom.id}' in template order.",
            prompt_source=PromptSource.AGENDA_ATOM,
            turn_purpose=TurnPurpose.OPENING,
        )

    if not state.synthesis_completed:
        return QuestionPlan(
            strategy=Strategy.SYNTHESIZE,
            target_atom_ids=[],
            phase=ConversationPhase.SYNTHESIS,
            reasoning_summary="All required agenda atoms were attempted once; ask one synthesis question.",
            prompt_source=PromptSource.SYSTEM_SYNTHESIS,
            turn_purpose=TurnPurpose.SYNTHESIS,
        )

    return QuestionPlan(
        strategy=Strategy.SYNTHESIZE,
        target_atom_ids=[],
        phase=ConversationPhase.SYNTHESIS,
        reasoning_summary="Synthesis is complete; prepare to finalize.",
        prompt_source=PromptSource.SYSTEM_SYNTHESIS,
        turn_purpose=TurnPurpose.SYNTHESIS,
    )


def plan_next_legacy_step(state: SessionState) -> QuestionPlan:
    phase = determine_phase(state)

    for question in state.template.question_bank:
        if not question.required:
            continue
        status = state.required_question_statuses.get(question.id, RequiredQuestionStatus.UNASKED)
        if status == RequiredQuestionStatus.ASKED_UNACCEPTABLE:
            attempts = state.question_unacceptable_counts.get(question.id, 0)
            needs_scaffolding = state.template.policies.allow_scaffolding and attempts >= 2
            strategy = Strategy.SCAFFOLD if needs_scaffolding else Strategy.CLARIFY
            return QuestionPlan(
                strategy=strategy,
                target_atom_ids=question.linked_atoms,
                target_question_id=question.id,
                phase=phase,
                reasoning_summary=(
                    f"Retry required question '{question.id}' because it is not yet acceptable."
                ),
                needs_scaffolding=needs_scaffolding,
                prompt_source=PromptSource.QUESTION_BANK,
                turn_purpose=TurnPurpose.REVISIT,
            )

    for question in state.template.question_bank:
        if question.required and state.required_question_statuses.get(
            question.id, RequiredQuestionStatus.UNASKED
        ) == RequiredQuestionStatus.UNASKED:
            return QuestionPlan(
                strategy=Strategy.PROBE if phase != ConversationPhase.WARMUP else Strategy.CLARIFY,
                target_atom_ids=question.linked_atoms,
                target_question_id=question.id,
                phase=phase,
                reasoning_summary=f"Ask required question '{question.id}' next.",
                prompt_source=PromptSource.QUESTION_BANK,
                turn_purpose=TurnPurpose.OPENING,
            )

    unmet_atoms = [
        atom.id
        for atom in state.template.agenda_atoms
        if atom.required and state.agenda_atom_statuses.get(atom.id) != AgendaStatus.MET
    ]
    if unmet_atoms:
        challenge_level = state.student_profile.preferences.get("challenge_level", "medium").lower()
        strategy = Strategy.CHALLENGE if challenge_level == "high" else Strategy.PROBE
        return QuestionPlan(
            strategy=strategy,
            target_atom_ids=[unmet_atoms[0]],
            target_question_id=None,
            phase=phase,
            reasoning_summary=f"Close the remaining gap on agenda atom '{unmet_atoms[0]}'.",
            prompt_source=PromptSource.QUESTION_BANK,
            turn_purpose=TurnPurpose.REVISIT,
        )

    return QuestionPlan(
        strategy=Strategy.SYNTHESIZE,
        target_atom_ids=[],
        target_question_id=None,
        phase=ConversationPhase.SYNTHESIS,
        reasoning_summary="All required checkpoints are satisfied; prepare to finalize.",
        prompt_source=PromptSource.SYSTEM_SYNTHESIS,
        turn_purpose=TurnPurpose.SYNTHESIS,
    )


def resolve_question(state: SessionState, plan: QuestionPlan) -> QuestionSpec:
    if plan.prompt_source == PromptSource.SYSTEM_SYNTHESIS:
        return QuestionSpec(
            id="agenda_synthesis",
            prompt="main takeaway from this reflection",
            required=False,
            intent_tags=["synthesis"],
            linked_atoms=[],
        )

    if state.template.uses_agenda_first():
        atom = get_atom_by_id(state.template, plan.target_atom_ids[0])
        if atom is None:
            raise ValueError(f"Unknown agenda atom id: {plan.target_atom_ids[0]}")
        suffix = "opening" if plan.turn_purpose == TurnPurpose.OPENING else "revisit"
        return QuestionSpec(
            id=f"agenda_{atom.id}_{suffix}",
            prompt=agenda_focus(atom.description),
            required=atom.required,
            intent_tags=[plan.strategy.value, plan.turn_purpose.value],
            linked_atoms=[atom.id],
        )

    return resolve_legacy_question(state, plan)


def resolve_legacy_question(state: SessionState, plan: QuestionPlan) -> QuestionSpec:
    if plan.target_question_id:
        question = get_question_by_id(state.template, plan.target_question_id)
        if question is None:
            raise ValueError(f"Unknown question id: {plan.target_question_id}")
        return question

    for question in state.template.question_bank:
        if question.required:
            continue
        if any(atom_id in plan.target_atom_ids for atom_id in question.linked_atoms):
            return question

    if not plan.target_atom_ids:
        return QuestionSpec(
            id="synthesis_followup",
            prompt="What is the strongest takeaway you want to leave this reflection with?",
            required=False,
            intent_tags=["synthesis"],
            linked_atoms=[],
        )

    atom = get_atom_by_id(state.template, plan.target_atom_ids[0])
    if atom is None:
        raise ValueError(f"Unknown agenda atom id: {plan.target_atom_ids[0]}")
    return QuestionSpec(
        id=f"followup_{atom.id}",
        prompt=f"Would you like to add a little more about {agenda_focus(atom.description)}?",
        required=False,
        intent_tags=[plan.strategy.value, "followup"],
        linked_atoms=[atom.id],
    )


def evaluate_pending_reply(state: SessionState) -> TurnEvaluation:
    if state.last_assistant_question is None:
        raise ValueError("No assistant question is available for evaluation.")
    if state.pending_student_reply is None:
        raise ValueError("No pending student reply is available for evaluation.")

    answer = state.pending_student_reply.strip()
    question = state.last_assistant_question
    linked_atoms = [
        get_atom_by_id(state.template, atom_id)
        for atom_id in question.linked_atoms
        if get_atom_by_id(state.template, atom_id) is not None
    ]
    missing_elements: list[str] = []
    atom_updates: list[AgendaAtomUpdate] = []

    for atom in linked_atoms:
        update = evaluate_atom(answer, atom, state.template)
        atom_updates.append(update)
        missing_elements.extend(update.missing)

    answer_acceptability = (
        AnswerAcceptability.ACCEPTABLE
        if atom_updates and all(update.status == AgendaStatus.MET for update in atom_updates)
        else AnswerAcceptability.UNACCEPTABLE
    )
    if not atom_updates:
        answer_acceptability = (
            AnswerAcceptability.ACCEPTABLE
            if count_words(answer) >= state.template.policies.min_student_words_per_turn
            else AnswerAcceptability.UNACCEPTABLE
        )
        if answer_acceptability == AnswerAcceptability.UNACCEPTABLE:
            missing_elements.append(
                f"Provide at least {state.template.policies.min_student_words_per_turn} words."
            )

    misconceptions = []
    if contains_any(answer, UNCERTAINTY_HINTS):
        misconceptions.append("Student expressed uncertainty that may need gentle follow-up.")

    question_status = RequiredQuestionStatus.ACCEPTABLE
    if state.template.uses_legacy_question_bank() and (
        question.required or question.question_id in state.required_question_statuses
    ):
        if answer_acceptability == AnswerAcceptability.ACCEPTABLE and not misconceptions:
            question_status = RequiredQuestionStatus.ACCEPTABLE
        else:
            question_status = RequiredQuestionStatus.ASKED_UNACCEPTABLE

    rubric_observations = build_rubric_observations(state.template, atom_updates)
    recommend_next_strategy = None
    if state.template.uses_legacy_question_bank() and answer_acceptability == AnswerAcceptability.UNACCEPTABLE:
        if count_words(answer) < state.template.policies.min_student_words_per_turn:
            recommend_next_strategy = Strategy.SCAFFOLD
        else:
            recommend_next_strategy = Strategy.CLARIFY

    return TurnEvaluation(
        answer_acceptability=answer_acceptability,
        question_status=question_status,
        agenda_atom_updates=atom_updates,
        rubric_observations=rubric_observations,
        misconceptions=misconceptions,
        missing_elements=unique_preserving_order(missing_elements),
        student_answer_summary=shorten(answer, width=160, placeholder="..."),
        recommend_next_strategy=recommend_next_strategy,
    )


def apply_turn_evaluation(state: SessionState, evaluation: TurnEvaluation) -> SessionState:
    if state.last_assistant_question is None or state.pending_student_reply is None:
        raise ValueError("State does not contain a question/reply pair to apply.")

    answer = state.pending_student_reply.strip()
    question_id = state.last_assistant_question.question_id
    state.transcript.append(
        TurnRecord(
            speaker="student",
            text=answer,
            turn_index=len(state.transcript) + 1,
            question_id=question_id,
        )
    )
    state.turn_index += 1

    if question_id in state.required_question_statuses:
        state.question_attempt_counts[question_id] = state.question_attempt_counts.get(question_id, 0) + 1
        state.required_question_statuses[question_id] = evaluation.question_status
        if evaluation.question_status == RequiredQuestionStatus.ASKED_UNACCEPTABLE:
            state.question_unacceptable_counts[question_id] = (
                state.question_unacceptable_counts.get(question_id, 0) + 1
            )
        else:
            state.question_unacceptable_counts[question_id] = 0

    for update in evaluation.agenda_atom_updates:
        current_status = state.agenda_atom_statuses.get(update.atom_id, AgendaStatus.UNKNOWN)
        state.agenda_atom_statuses[update.atom_id] = pick_stronger_status(current_status, update.status)
        state.agenda_atom_missing[update.atom_id] = update.missing
        if update.evidence:
            evidence_list = state.agenda_atom_evidence.setdefault(update.atom_id, [])
            if update.evidence not in evidence_list:
                evidence_list.append(update.evidence)

    for observation in evaluation.rubric_observations:
        current_score = state.rubric_progress.get(observation.rubric_id, 0)
        state.rubric_progress[observation.rubric_id] = max(current_score, observation.score)

    state.open_issues = unique_preserving_order(
        [*evaluation.missing_elements, *evaluation.misconceptions]
    )
    state.pending_student_reply = None
    if state.last_plan is not None and state.last_plan.turn_purpose == TurnPurpose.SYNTHESIS:
        state.synthesis_completed = True
    state.conversation_phase = determine_phase(state)
    return state


def is_session_complete(state: SessionState) -> bool:
    if state.template.uses_agenda_first():
        return state.synthesis_completed

    all_atoms_met = all(
        state.agenda_atom_statuses.get(atom.id) == AgendaStatus.MET
        for atom in state.template.agenda_atoms
        if atom.required
    )
    all_required_questions_acceptable = all(
        status == RequiredQuestionStatus.ACCEPTABLE
        for status in state.required_question_statuses.values()
    )
    return all_atoms_met and all_required_questions_acceptable


def pick_stronger_status(current: AgendaStatus, new: AgendaStatus) -> AgendaStatus:
    order = {
        AgendaStatus.UNKNOWN: 0,
        AgendaStatus.PARTIALLY_MET: 1,
        AgendaStatus.MET: 2,
    }
    return new if order[new] >= order[current] else current


def evaluate_atom(answer: str, atom: AgendaAtom, template: ReflectionTemplate) -> AgendaAtomUpdate:
    rules = atom.acceptance_rules
    missing: list[str] = []
    effective_min_words = max(rules.min_words, template.policies.min_student_words_per_turn)
    if count_words(answer) < effective_min_words:
        missing.append(f"Provide at least {effective_min_words} words for '{atom.id}'.")
    if rules.required_terms:
        missing_terms = [term for term in rules.required_terms if term.lower() not in answer.lower()]
        if missing_terms:
            missing.append(f"Include required terms: {', '.join(missing_terms)}.")
    if rules.must_include_concrete_position and not contains_any(answer, POSITION_HINTS):
        missing.append("State a concrete position or claim.")
    if rules.must_include_example and not contains_any(answer, EXAMPLE_HINTS):
        missing.append("Add a specific example.")
    if rules.must_address_counterargument and not contains_any(answer, COUNTERARGUMENT_HINTS):
        missing.append("Address a counterargument or tension.")
    if rules.must_include_next_action and not contains_any(answer, NEXT_ACTION_HINTS):
        missing.append("Name a next action or follow-up step.")

    status = AgendaStatus.MET
    if missing:
        status = AgendaStatus.PARTIALLY_MET if count_words(answer) > 0 else AgendaStatus.UNKNOWN

    return AgendaAtomUpdate(
        atom_id=atom.id,
        status=status,
        evidence=shorten(answer.strip(), width=180, placeholder="..."),
        missing=missing,
    )


def build_rubric_observations(
    template: ReflectionTemplate,
    atom_updates: list[AgendaAtomUpdate],
) -> list[RubricObservation]:
    status_by_atom = {update.atom_id: update.status for update in atom_updates}
    observations: list[RubricObservation] = []
    for criterion in template.rubric:
        linked_atom_statuses = [
            status_by_atom[atom.id]
            for atom in template.agenda_atoms
            if criterion.id in atom.linked_rubric_criteria and atom.id in status_by_atom
        ]
        if not linked_atom_statuses:
            continue
        score = criterion.scale_min
        if all(status == AgendaStatus.MET for status in linked_atom_statuses):
            score = criterion.scale_max
        elif any(status == AgendaStatus.PARTIALLY_MET for status in linked_atom_statuses):
            score = max(criterion.scale_min, criterion.scale_max - 1)
        observations.append(
            RubricObservation(
                rubric_id=criterion.id,
                score=score,
                rationale=f"Updated from linked agenda atoms for '{criterion.id}'.",
            )
        )
    return observations


def get_question_by_id(template: ReflectionTemplate, question_id: str) -> QuestionSpec | None:
    for question in template.question_bank:
        if question.id == question_id:
            return question
    return None


def get_atom_by_id(template: ReflectionTemplate, atom_id: str) -> AgendaAtom | None:
    for atom in template.agenda_atoms:
        if atom.id == atom_id:
            return atom
    return None


def get_rubric_by_id(template: ReflectionTemplate, rubric_id: str) -> RubricCriterion | None:
    for criterion in template.rubric:
        if criterion.id == rubric_id:
            return criterion
    return None
