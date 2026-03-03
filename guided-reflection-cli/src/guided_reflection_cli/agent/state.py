"""Pydantic models for the lean LangGraph agent."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AgendaStatus(str, Enum):
    UNKNOWN = "unknown"
    PARTIALLY_MET = "partially_met"
    MET = "met"


class PlanAction(str, Enum):
    ASK_AGENDA = "ask_agenda"
    PIVOT_TOPIC = "pivot_topic"
    SCAFFOLD = "scaffold"
    SYNTHESIZE = "synthesize"
    STOP_NOW = "stop_now"


class StopReason(str, Enum):
    COMPLETED = "completed"
    MAX_TURNS = "max_turns"
    STUDENT_EXIT = "student_exit"
    INTERRUPT = "interrupt"
    MODEL_ERROR = "model_error"


class ConversationPhase(str, Enum):
    WARMUP = "warmup"
    PROBING = "probing"
    SYNTHESIS = "synthesis"
    FINALIZE = "finalize"


class AcceptanceRules(BaseModel):
    min_words: int = 0
    required_terms: list[str] = Field(default_factory=list)
    must_include_example: bool = False

    @field_validator("min_words")
    @classmethod
    def non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("min_words must be >= 0")
        return value


class AgendaAtom(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    description: str
    required: bool = True
    acceptance_rules: AcceptanceRules = Field(default_factory=AcceptanceRules)


class AgendaFile(BaseModel):
    model_config = ConfigDict(extra="allow")

    template_id: str = "agenda"
    title: str = "Guided Reflection"
    topic: str
    agenda_atoms: list[AgendaAtom]
    max_turns: int = 12
    tone: str = "supportive"


class StudentProfile(BaseModel):
    model_config = ConfigDict(extra="allow")

    student_id: str
    display_name: str = "Student"
    course: str | None = None
    strengths: list[str] = Field(default_factory=list)
    growth_areas: list[str] = Field(default_factory=list)
    preferences: dict[str, str] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class MemorySnippet(BaseModel):
    snippet_id: str
    text: str
    source: str = ""


class Turn(BaseModel):
    speaker: Literal["assistant", "student"]
    text: str
    question_id: str | None = None
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


class PlanDecision(BaseModel):
    action: PlanAction
    target_atom_id: str | None = None
    reason: str = ""
    needs_scaffold: bool = False
    needs_context: bool = False
    stop_signal: bool = False


class AgendaUpdate(BaseModel):
    atom_id: str
    status: AgendaStatus
    missing: list[str] = Field(default_factory=list)


class EvalResult(BaseModel):
    agenda_updates: list[AgendaUpdate] = Field(default_factory=list)
    stop_signal: bool = False
    open_issues: list[str] = Field(default_factory=list)


class SessionState(BaseModel):
    session_id: str
    agenda: AgendaFile
    student: StudentProfile
    conversation_phase: ConversationPhase = ConversationPhase.WARMUP
    turn_index: int = 0
    asked_atoms: list[str] = Field(default_factory=list)
    agenda_statuses: dict[str, AgendaStatus] = Field(default_factory=dict)
    open_issues: list[str] = Field(default_factory=list)
    transcript: list[Turn] = Field(default_factory=list)
    stall_counts: dict[str, int] = Field(default_factory=dict)
    memory_snippets: list[MemorySnippet] = Field(default_factory=list)
    available_context: dict[str, int] = Field(default_factory=dict)
    last_plan: PlanDecision | None = None
    stop_reason: StopReason | None = None
    notes: list[str] = Field(default_factory=list)
    output_dir: Path | None = None
    summary: dict[str, Any] | None = None

    @classmethod
    def initialize(
        cls,
        agenda: AgendaFile,
        student: StudentProfile,
        memory_snippets: list[MemorySnippet],
        notes: list[str],
        session_id: str,
        output_dir: Path | None,
    ) -> "SessionState":
        return cls(
            session_id=session_id,
            agenda=agenda,
            student=student,
            agenda_statuses={atom.id: AgendaStatus.UNKNOWN for atom in agenda.agenda_atoms},
            stall_counts={atom.id: 0 for atom in agenda.agenda_atoms},
            memory_snippets=memory_snippets,
            available_context={
                "notes_count": len(notes),
                "memory_count": len(memory_snippets),
            },
            notes=notes,
            output_dir=output_dir,
        )

    def agenda_atom(self, atom_id: str | None) -> AgendaAtom | None:
        if atom_id is None:
            return None
        for atom in self.agenda.agenda_atoms:
            if atom.id == atom_id:
                return atom
        return None

    def required_atoms_remaining(self) -> list[str]:
        return [
            atom.id
            for atom in self.agenda.agenda_atoms
            if atom.required and self.agenda_statuses.get(atom.id, AgendaStatus.UNKNOWN) != AgendaStatus.MET
        ]

    def transcript_tail(self, turns: int = 6) -> list[Turn]:
        return self.transcript[-turns:]
