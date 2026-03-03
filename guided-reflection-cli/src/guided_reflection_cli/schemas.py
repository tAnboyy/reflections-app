"""Pydantic schemas for templates, runtime state, and output artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AgendaStatus(str, Enum):
    UNKNOWN = "unknown"
    PARTIALLY_MET = "partially_met"
    MET = "met"


class RequiredQuestionStatus(str, Enum):
    UNASKED = "unasked"
    ASKED_UNACCEPTABLE = "asked_unacceptable"
    ACCEPTABLE = "acceptable"


class ConversationPhase(str, Enum):
    WARMUP = "warmup"
    PROBING = "probing"
    SYNTHESIS = "synthesis"
    FINALIZE = "finalize"


class StopReason(str, Enum):
    COMPLETED = "completed"
    MAX_TURNS = "max_turns"
    STUDENT_EXIT = "student_exit"
    INTERRUPT = "interrupt"
    EVALUATION_ERROR = "evaluation_error"


class Strategy(str, Enum):
    CLARIFY = "clarify"
    PROBE = "probe"
    CHALLENGE = "challenge"
    SCAFFOLD = "scaffold"
    SYNTHESIZE = "synthesize"


class AnswerAcceptability(str, Enum):
    ACCEPTABLE = "acceptable"
    UNACCEPTABLE = "unacceptable"


class AcceptanceRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_words: int = 0
    required_terms: list[str] = Field(default_factory=list)
    must_include_concrete_position: bool = False
    must_include_example: bool = False
    must_address_counterargument: bool = False
    must_include_next_action: bool = False

    @field_validator("min_words")
    @classmethod
    def validate_min_words(cls, value: int) -> int:
        if value < 0:
            raise ValueError("min_words must be >= 0")
        return value


class AssignmentSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str
    deliverable: str = "Guided reflection"


class AgendaAtom(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    required: bool = True
    acceptance_rules: AcceptanceRules = Field(default_factory=AcceptanceRules)
    linked_rubric_criteria: list[str] = Field(default_factory=list)


class QuestionSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    prompt: str
    required: bool = False
    intent_tags: list[str] = Field(default_factory=list)
    linked_atoms: list[str] = Field(default_factory=list)


class RubricCriterion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    scale_min: int = 0
    scale_max: int = 3

    @model_validator(mode="after")
    def validate_scale(self) -> "RubricCriterion":
        if self.scale_max < self.scale_min:
            raise ValueError("scale_max must be >= scale_min")
        return self


class SessionPolicies(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tone: str = "supportive"
    max_turns: int = 12
    min_student_words_per_turn: int = 15
    allow_scaffolding: bool = True
    completion_mode: Literal["required_atoms_and_required_questions"] = (
        "required_atoms_and_required_questions"
    )
    final_summary_style: str = "concise"

    @field_validator("max_turns", "min_student_words_per_turn")
    @classmethod
    def validate_positive_ints(cls, value: int, info: Any) -> int:
        minimum = 1 if info.field_name == "max_turns" else 0
        if value < minimum:
            raise ValueError(f"{info.field_name} must be >= {minimum}")
        return value


class ReflectionTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    template_id: str
    version: int
    title: str
    topic: str
    assignment: AssignmentSpec
    agenda_atoms: list[AgendaAtom]
    question_bank: list[QuestionSpec]
    rubric: list[RubricCriterion]
    policies: SessionPolicies = Field(default_factory=SessionPolicies)

    @field_validator("version")
    @classmethod
    def validate_version(cls, value: int) -> int:
        if value < 1:
            raise ValueError("version must be >= 1")
        return value

    @model_validator(mode="after")
    def validate_links(self) -> "ReflectionTemplate":
        atom_ids = _ensure_unique_ids(self.agenda_atoms, "agenda_atoms")
        question_ids = _ensure_unique_ids(self.question_bank, "question_bank")
        rubric_ids = _ensure_unique_ids(self.rubric, "rubric")

        for question in self.question_bank:
            for atom_id in question.linked_atoms:
                if atom_id not in atom_ids:
                    raise ValueError(
                        f"question_bank.{question.id}.linked_atoms references unknown atom '{atom_id}'"
                    )
        for atom in self.agenda_atoms:
            for rubric_id in atom.linked_rubric_criteria:
                if rubric_id not in rubric_ids:
                    raise ValueError(
                        "agenda_atoms."
                        f"{atom.id}.linked_rubric_criteria references unknown rubric '{rubric_id}'"
                    )

        _ = question_ids
        return self


class StudentProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_id: str
    display_name: str = "Student"
    course: str = ""
    standing_summary: str = ""
    preferences: dict[str, str] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    growth_areas: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class MemorySnippet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    snippet_id: str
    text: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class TurnRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker: Literal["assistant", "student"]
    text: str
    turn_index: int
    question_id: str | None = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


class QuestionPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: Strategy
    target_atom_ids: list[str] = Field(default_factory=list)
    target_question_id: str | None = None
    phase: ConversationPhase
    reasoning_summary: str
    needs_scaffolding: bool = False


class GeneratedQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_text: str
    question_id: str
    intent_tags: list[str] = Field(default_factory=list)
    phase: ConversationPhase
    linked_atoms: list[str] = Field(default_factory=list)
    required: bool = False


class AgendaAtomUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    atom_id: str
    status: AgendaStatus
    evidence: str = ""
    missing: list[str] = Field(default_factory=list)


class RubricObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rubric_id: str
    score: int
    rationale: str


class TurnEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer_acceptability: AnswerAcceptability
    question_status: RequiredQuestionStatus
    agenda_atom_updates: list[AgendaAtomUpdate] = Field(default_factory=list)
    rubric_observations: list[RubricObservation] = Field(default_factory=list)
    misconceptions: list[str] = Field(default_factory=list)
    missing_elements: list[str] = Field(default_factory=list)
    student_answer_summary: str
    recommend_next_strategy: Strategy | None = None


class AgendaCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    atom_id: str
    description: str
    status: AgendaStatus
    evidence: list[str] = Field(default_factory=list)


class QuestionCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question_id: str
    prompt: str
    status: RequiredQuestionStatus
    attempts: int = 0


class RubricScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rubric_id: str
    description: str
    score: int
    max_score: int


class FinalReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    final_student_reflection: str
    agenda_completion_report: list[AgendaCompletion]
    required_question_report: list[QuestionCompletion]
    rubric_scores: list[RubricScore]
    teacher_notes: list[str] = Field(default_factory=list)
    session_summary: str
    stop_reason: StopReason


class SessionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    template: ReflectionTemplate
    student_profile: StudentProfile
    conversation_phase: ConversationPhase = ConversationPhase.WARMUP
    turn_index: int = 0
    asked_question_ids: list[str] = Field(default_factory=list)
    required_question_statuses: dict[str, RequiredQuestionStatus] = Field(default_factory=dict)
    question_attempt_counts: dict[str, int] = Field(default_factory=dict)
    question_unacceptable_counts: dict[str, int] = Field(default_factory=dict)
    agenda_atom_statuses: dict[str, AgendaStatus] = Field(default_factory=dict)
    agenda_atom_evidence: dict[str, list[str]] = Field(default_factory=dict)
    rubric_progress: dict[str, int] = Field(default_factory=dict)
    open_issues: list[str] = Field(default_factory=list)
    transcript: list[TurnRecord] = Field(default_factory=list)
    last_plan: QuestionPlan | None = None
    last_assistant_question: GeneratedQuestion | None = None
    pending_student_reply: str | None = None
    stop_reason: StopReason | None = None
    final_summary: str = ""
    teacher_notes: list[str] = Field(default_factory=list)
    debug_trace: list[str] = Field(default_factory=list)
    final_report: FinalReport | None = None
    memory_snippets: list[MemorySnippet] = Field(default_factory=list)


def _ensure_unique_ids(items: list[Any], field_name: str) -> set[str]:
    seen: set[str] = set()
    for item in items:
        if item.id in seen:
            raise ValueError(f"duplicate id '{item.id}' found in {field_name}")
        seen.add(item.id)
    return seen
