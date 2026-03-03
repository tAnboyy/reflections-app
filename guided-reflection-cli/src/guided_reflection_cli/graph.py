"""LangGraph-compatible session orchestration with a local fallback."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from guided_reflection_cli.evaluation import (
    apply_turn_evaluation,
    evaluate_pending_reply,
    initialize_state_maps,
    is_session_complete,
    plan_next_step,
    resolve_question,
)
from guided_reflection_cli.llm import ReflectionLLM
from guided_reflection_cli.memory import MemoryProvider, NullMemoryProvider
from guided_reflection_cli.reporting import build_final_report
from guided_reflection_cli.schemas import (
    ConversationPhase,
    ReflectionTemplate,
    SessionState,
    StopReason,
    StudentProfile,
    TurnRecord,
)

try:  # pragma: no cover - depends on external install
    from langgraph.graph import END, START, StateGraph
except ImportError:  # pragma: no cover - local fallback for offline development
    END = "__end__"
    START = "__start__"

    class _CompiledFallbackGraph:
        def __init__(self, nodes: dict[str, Any], edges: dict[str, str], conditionals: dict[str, Any]):
            self.nodes = nodes
            self.edges = edges
            self.conditionals = conditionals

        def invoke(self, state: dict[str, Any]) -> dict[str, Any]:
            current = self.edges[START]
            current_state = dict(state)
            while current != END:
                update = self.nodes[current](current_state) or {}
                current_state.update(update)
                if current in self.conditionals:
                    current = self.conditionals[current](current_state)
                else:
                    current = self.edges.get(current, END)
            return current_state

    class StateGraph:  # type: ignore[override]
        def __init__(self, state_schema: Any):
            _ = state_schema
            self._nodes: dict[str, Any] = {}
            self._edges: dict[str, str] = {}
            self._conditionals: dict[str, Any] = {}

        def add_node(self, name: str, func: Any) -> None:
            self._nodes[name] = func

        def add_edge(self, start: str, end: str) -> None:
            self._edges[start] = end

        def add_conditional_edges(self, start: str, condition: Any, mapping: dict[str, str]) -> None:
            self._conditionals[start] = lambda state: mapping[condition(state)]

        def compile(self) -> _CompiledFallbackGraph:
            return _CompiledFallbackGraph(self._nodes, self._edges, self._conditionals)


class GuidedReflectionGraph:
    """Stateful turn controller for guided reflection sessions."""

    def __init__(self, llm: ReflectionLLM, memory_provider: MemoryProvider | None = None):
        self.llm = llm
        self.memory_provider = memory_provider or NullMemoryProvider()
        self._compiled_graph = self._build_graph()

    def initialize_session(
        self,
        template: ReflectionTemplate,
        student_profile: StudentProfile,
        max_turns_override: int | None = None,
    ) -> SessionState:
        template_copy = template.model_copy(deep=True)
        if max_turns_override is not None:
            template_copy.policies.max_turns = max_turns_override
        (
            required_question_statuses,
            question_attempt_counts,
            question_unacceptable_counts,
            agenda_atom_statuses,
            agenda_atom_evidence,
            rubric_progress,
        ) = initialize_state_maps(template_copy)
        return SessionState(
            session_id=str(uuid4()),
            template=template_copy,
            student_profile=student_profile,
            conversation_phase=ConversationPhase.WARMUP,
            required_question_statuses=required_question_statuses,
            question_attempt_counts=question_attempt_counts,
            question_unacceptable_counts=question_unacceptable_counts,
            agenda_atom_statuses=agenda_atom_statuses,
            agenda_atom_evidence=agenda_atom_evidence,
            rubric_progress=rubric_progress,
            memory_snippets=self.memory_provider.retrieve(
                student_profile.student_id,
                query=f"{template_copy.topic} {template_copy.assignment.statement}",
                limit=3,
            ),
        )

    def step(self, state: SessionState) -> SessionState:
        state_dict = self._compiled_graph.invoke(state.model_dump())
        return SessionState.model_validate(state_dict)

    def _build_graph(self) -> Any:
        graph = StateGraph(dict)
        graph.add_node("route_turn", self._route_turn)
        graph.add_node("plan_next_step", self._plan_next_step)
        graph.add_node("generate_question", self._generate_question)
        graph.add_node("evaluate_response", self._evaluate_response)
        graph.add_node("decide_next_action", self._decide_next_action)
        graph.add_node("finalize_submission", self._finalize_submission)

        graph.add_edge(START, "route_turn")
        graph.add_conditional_edges(
            "route_turn",
            self._route_condition,
            {
                "plan_next_step": "plan_next_step",
                "evaluate_response": "evaluate_response",
                "finalize_submission": "finalize_submission",
                "end": END,
            },
        )
        graph.add_edge("plan_next_step", "generate_question")
        graph.add_edge("generate_question", END)
        graph.add_edge("evaluate_response", "decide_next_action")
        graph.add_conditional_edges(
            "decide_next_action",
            self._decide_condition,
            {
                "finalize_submission": "finalize_submission",
                "end": END,
            },
        )
        graph.add_edge("finalize_submission", END)
        return graph.compile()

    def _route_turn(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        state = SessionState.model_validate(state_dict)
        state.debug_trace.append(
            f"Routing turn with stop_reason={state.stop_reason} pending_reply={bool(state.pending_student_reply)}"
        )
        return state.model_dump(mode="python")

    def _route_condition(self, state_dict: dict[str, Any]) -> str:
        state = SessionState.model_validate(state_dict)
        if state.stop_reason is not None and state.final_report is None:
            return "finalize_submission"
        if state.pending_student_reply is not None:
            return "evaluate_response"
        if state.stop_reason is None:
            return "plan_next_step"
        return "end"

    def _plan_next_step(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        state = SessionState.model_validate(state_dict)
        state.last_plan = plan_next_step(state)
        state.conversation_phase = state.last_plan.phase
        state.debug_trace.append(f"Planned: {state.last_plan.reasoning_summary}")
        return state.model_dump(mode="python")

    def _generate_question(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        state = SessionState.model_validate(state_dict)
        if state.last_plan is None:
            raise ValueError("last_plan must be set before generating a question.")
        question = resolve_question(state, state.last_plan)
        generated = self.llm.generate_question(
            state=state,
            plan=state.last_plan,
            question_id=question.id,
            base_prompt=question.prompt,
            linked_atoms=question.linked_atoms,
            required=question.required,
            intent_tags=question.intent_tags,
        )
        state.last_assistant_question = generated
        state.asked_question_ids.append(generated.question_id)
        state.transcript.append(
            TurnRecord(
                speaker="assistant",
                text=generated.question_text,
                turn_index=len(state.transcript) + 1,
                question_id=generated.question_id,
            )
        )
        return state.model_dump(mode="python")

    def _evaluate_response(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        state = SessionState.model_validate(state_dict)
        try:
            evaluation = evaluate_pending_reply(state)
        except Exception as exc:
            state.stop_reason = StopReason.EVALUATION_ERROR
            state.debug_trace.append(f"Evaluation error: {exc}")
            return state.model_dump(mode="python")
        state = apply_turn_evaluation(state, evaluation)
        state.debug_trace.append(
            f"Evaluation acceptability={evaluation.answer_acceptability.value} "
            f"missing={evaluation.missing_elements}"
        )
        return state.model_dump(mode="python")

    def _decide_next_action(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        state = SessionState.model_validate(state_dict)
        if is_session_complete(state):
            state.stop_reason = StopReason.COMPLETED
            state.conversation_phase = ConversationPhase.FINALIZE
        elif state.turn_index >= state.template.policies.max_turns:
            state.stop_reason = StopReason.MAX_TURNS
            state.conversation_phase = ConversationPhase.FINALIZE
        return state.model_dump(mode="python")

    def _decide_condition(self, state_dict: dict[str, Any]) -> str:
        state = SessionState.model_validate(state_dict)
        if state.stop_reason is not None:
            return "finalize_submission"
        return "end"

    def _finalize_submission(self, state_dict: dict[str, Any]) -> dict[str, Any]:
        state = SessionState.model_validate(state_dict)
        if state.stop_reason is None:
            state.stop_reason = StopReason.COMPLETED
        state.conversation_phase = ConversationPhase.FINALIZE
        state.final_report = build_final_report(state, self.llm)
        state.final_summary = state.final_report.final_student_reflection
        state.teacher_notes = state.final_report.teacher_notes
        return state.model_dump(mode="python")
