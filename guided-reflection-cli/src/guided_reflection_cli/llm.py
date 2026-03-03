"""LLM provider abstraction for question phrasing and final summaries."""

from __future__ import annotations

from abc import ABC, abstractmethod
from textwrap import shorten

from pydantic import BaseModel, ConfigDict, Field

from guided_reflection_cli.prompts import (
    build_final_report_messages,
    build_question_generation_messages,
)
from guided_reflection_cli.schemas import GeneratedQuestion, QuestionPlan, SessionState
from guided_reflection_cli.settings import Settings


class NarrativeBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    final_student_reflection: str
    session_summary: str
    teacher_notes: list[str] = Field(default_factory=list)


class ReflectionLLM(ABC):
    """Interface for model-backed language generation."""

    @abstractmethod
    def generate_question(
        self,
        state: SessionState,
        plan: QuestionPlan,
        question_id: str,
        base_prompt: str,
        linked_atoms: list[str],
        required: bool,
        intent_tags: list[str],
    ) -> GeneratedQuestion:
        ...

    @abstractmethod
    def generate_narrative(self, state: SessionState) -> NarrativeBundle:
        ...


class FakeReflectionLLM(ReflectionLLM):
    """Deterministic provider used for tests and offline runs."""

    def generate_question(
        self,
        state: SessionState,
        plan: QuestionPlan,
        question_id: str,
        base_prompt: str,
        linked_atoms: list[str],
        required: bool,
        intent_tags: list[str],
    ) -> GeneratedQuestion:
        interest_hint = ""
        if state.student_profile.notes:
            interest_hint = f" If helpful, connect it to {state.student_profile.notes[0].rstrip('.')}."

        starter = ""
        if plan.strategy.value == "scaffold":
            starter = " Answer in 2-3 sentences. You can start with: 'My position is ... because ...'."
        elif plan.strategy.value == "clarify":
            starter = " Be specific and concrete."
        elif plan.strategy.value == "challenge":
            starter = " Include one tension or counterpoint."
        elif plan.strategy.value == "synthesize":
            starter = " Focus on what matters most."

        return GeneratedQuestion(
            question_text=f"{base_prompt}{starter}{interest_hint}",
            question_id=question_id,
            intent_tags=intent_tags,
            phase=plan.phase,
            linked_atoms=linked_atoms,
            required=required,
        )

    def generate_narrative(self, state: SessionState) -> NarrativeBundle:
        student_turns = [turn.text for turn in state.transcript if turn.speaker == "student"]
        assistant_turns = [turn.text for turn in state.transcript if turn.speaker == "assistant"]
        latest_student_text = student_turns[-1] if student_turns else "The student provided limited detail."
        session_summary = (
            f"The session covered {len(student_turns)} student turns and "
            f"{len(assistant_turns)} tutor prompts focused on {state.template.topic}."
        )
        teacher_notes = []
        if state.open_issues:
            teacher_notes.append(f"Remaining issues: {', '.join(state.open_issues[:3])}.")
        return NarrativeBundle(
            final_student_reflection=shorten(latest_student_text, width=320, placeholder="..."),
            session_summary=session_summary,
            teacher_notes=teacher_notes,
        )


class OpenAIReflectionLLM(ReflectionLLM):
    """LangChain-backed provider for live question phrasing and summaries."""

    def __init__(self, settings: Settings):
        settings.validate_provider_requirements()
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as exc:  # pragma: no cover - depends on external install
            raise RuntimeError(
                "langchain-openai is required for LLM_PROVIDER='openai'. "
                "Install guided-reflection-cli dependencies or use LLM_PROVIDER=fake."
            ) from exc
        self._model = ChatOpenAI(
            model=settings.openai_model,
            api_key=settings.openai_api_key,
            temperature=0.2,
        )

    def generate_question(
        self,
        state: SessionState,
        plan: QuestionPlan,
        question_id: str,
        base_prompt: str,
        linked_atoms: list[str],
        required: bool,
        intent_tags: list[str],
    ) -> GeneratedQuestion:
        structured_model = self._model.with_structured_output(GeneratedQuestion)
        transcript_excerpt = "\n".join(
            f"{turn.speaker}: {turn.text}" for turn in state.transcript[-4:]
        )
        messages = build_question_generation_messages(
            template=state.template,
            student_profile=state.student_profile,
            plan=plan,
            base_prompt=base_prompt,
            transcript_excerpt=transcript_excerpt,
        )
        rendered = structured_model.invoke(messages)
        return rendered.model_copy(
            update={
                "question_id": question_id,
                "phase": plan.phase,
                "linked_atoms": linked_atoms,
                "required": required,
                "intent_tags": intent_tags or rendered.intent_tags,
            }
        )

    def generate_narrative(self, state: SessionState) -> NarrativeBundle:
        structured_model = self._model.with_structured_output(NarrativeBundle)
        return structured_model.invoke(build_final_report_messages(state))


def build_llm_client(settings: Settings) -> ReflectionLLM:
    if settings.llm_provider == "fake":
        return FakeReflectionLLM()
    if settings.llm_provider == "openai":
        return OpenAIReflectionLLM(settings)
    if settings.llm_provider == "ollama":
        settings.validate_provider_requirements()
    raise RuntimeError(f"Unsupported LLM provider: {settings.llm_provider}")
