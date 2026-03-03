"""LLM provider abstraction for question phrasing and final summaries."""

from __future__ import annotations

from abc import ABC, abstractmethod
from textwrap import shorten

from pydantic import BaseModel, ConfigDict, Field

from guided_reflection_cli.prompts import (
    build_final_report_messages,
    build_question_generation_messages,
)
from guided_reflection_cli.schemas import GeneratedQuestion, PromptSource, QuestionPlan, SessionState, TurnPurpose
from guided_reflection_cli.settings import Settings
from guided_reflection_cli.utils import contains_any


UNCERTAINTY_HINTS = ["i don't know", "not sure", "confused", "unclear", "maybe"]
OPTIONAL_SCAFFOLD = "If it helps, you can name one example, one reason it matters, or one next step."


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
        if plan.prompt_source == PromptSource.SYSTEM_SYNTHESIS:
            question_text = self._compose_gentle_question(
                state=state,
                prompt="Looking back, what feels like the main takeaway from this reflection?",
                plan=plan,
            )
        elif state.template.uses_agenda_first():
            prompt = self._agenda_prompt(base_prompt, plan.turn_purpose)
            question_text = self._compose_gentle_question(state=state, prompt=prompt, plan=plan)
        else:
            question_text = self._compose_gentle_question(state=state, prompt=base_prompt, plan=plan)

        return GeneratedQuestion(
            question_text=question_text,
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

    def _agenda_prompt(self, focus: str, turn_purpose: TurnPurpose) -> str:
        if turn_purpose == TurnPurpose.REVISIT:
            return (
                f"Earlier you touched on {focus}. Before we wrap up, what would you want a reader to understand "
                "about it?"
            )
        return f"Let's start with {focus}. What feels most important for you to say here?"

    def _compose_gentle_question(self, state: SessionState, prompt: str, plan: QuestionPlan) -> str:
        acknowledgment = _build_acknowledgment(state)
        needs_scaffold = plan.needs_scaffolding or _student_sounds_uncertain(state)

        if needs_scaffold and _looks_like_single_sentence(prompt):
            return f"{prompt} {OPTIONAL_SCAFFOLD}"
        if acknowledgment:
            return f"{acknowledgment} {prompt}"
        return prompt


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


def _build_acknowledgment(state: SessionState) -> str:
    student_turns = [turn.text for turn in state.transcript if turn.speaker == "student"]
    if not student_turns:
        return ""
    latest = student_turns[-1]
    if contains_any(latest, UNCERTAINTY_HINTS):
        return ""
    if len(latest.split()) >= 8:
        return "That gives us a useful direction."
    return "You're starting to narrow it down."


def _student_sounds_uncertain(state: SessionState) -> bool:
    student_turns = [turn.text for turn in state.transcript if turn.speaker == "student"]
    if not student_turns:
        return False
    return contains_any(student_turns[-1], UNCERTAINTY_HINTS)


def _looks_like_single_sentence(text: str) -> bool:
    sentence_endings = text.count(".") + text.count("?") + text.count("!")
    return sentence_endings <= 1
