"""LangGraph-driven guided reflection agent."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Any
from uuid import uuid4

import yaml
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from rich.console import Console

from guided_reflection_cli.agent.memory import (
    append_notes,
    load_notes,
    load_profile,
    load_recent_summaries,
    load_submissions,
    merge_snippets,
)
from guided_reflection_cli.agent.state import (
    AgendaAtom,
    AgendaFile,
    AgendaStatus,
    EvalResult,
    PlanAction,
    PlanDecision,
    ConversationPhase,
    SessionState,
    StopReason,
    Turn,
    AgendaUpdate,
)
from guided_reflection_cli.agent.storage import persist_run


PROMPTS = yaml.safe_load((Path(__file__).parent / "prompts.yaml").read_text(encoding="utf-8"))

EXIT_PATTERNS = [
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
    "im done",
    "done with the questions",
    "exit",
    "quit",
]

STALL_PATTERNS = [
    "cant think",
    "can't think",
    "dont know",
    "don't know",
    "not sure",
    "already said",
    "already talked",
    "already mentioned",
    "told you already",
    "already talked about it",
    "already talked about this",
]


def render(template: str, context: Dict[str, Any]) -> str:
    rendered = template
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", str(value))
    return rendered


def call_json(model: ChatOpenAI, system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    response = model.invoke(messages)
    content = getattr(response, "content", "") or ""
    content = content.strip()
    if content.startswith("```"):
        content = content.strip("`")
        if content.startswith("json"):
            content = content[4:].strip()
    try:
        return json.loads(content)
    except Exception:
        return {}


def call_text(model: ChatOpenAI, system_prompt: str, user_prompt: str) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    response = model.invoke(messages)
    content = getattr(response, "content", "") or ""
    return content.strip()


def reply_signals_exit(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    for phrase in EXIT_PATTERNS:
        if phrase in normalized:
            return True
    return False


def reply_signals_stall(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9\s]", " ", text.lower())
    return any(phrase in normalized for phrase in STALL_PATTERNS)


def agenda_focus_text(state: SessionState, atom_id: str | None) -> str:
    atom = state.agenda_atom(atom_id)
    if atom:
        return atom.description
    return "the main takeaway from this reflection"


def last_student_turn_text(session: SessionState) -> str:
    for turn in reversed(session.transcript):
        if turn.speaker == "student":
            return turn.text
    return ""


@dataclass
class RunConfig:
    agenda_path: Path | None
    agenda_text: str | None
    student_id: str
    profile_path: Path | None
    submissions: list[Path]
    max_turns: int | None
    model: str
    output_dir: Path | None
    input_func: Callable[[str], str]
    console: Console


def load_agenda(path: Path | None, inline_text: str | None, max_turns_override: int | None) -> AgendaFile:
    # Inline text agenda takes precedence
    if inline_text:
        text = inline_text.strip()
        topic = " ".join(text.split()[:8]) or "Reflection"
        return AgendaFile(
            template_id="text-agenda",
            title="Text Agenda",
            topic=topic,
            agenda_atoms=[
                AgendaAtom(id="focus", description=text, required=True),
            ],
            max_turns=max_turns_override or 12,
            tone="supportive",
        )
    if path is None:
        raise ValueError("Agenda path or inline text is required.")
    content = path.read_text(encoding="utf-8")
    try:
        raw = yaml.safe_load(content) or {}
        if not isinstance(raw, dict):
            raise ValueError("Not a mapping")
    except Exception:
        # Treat as plain text agenda
        text = content.strip()
        topic = " ".join(text.split()[:8]) or "Reflection"
        return AgendaFile(
            template_id=path.stem,
            title="Text Agenda",
            topic=topic,
            agenda_atoms=[AgendaAtom(id="focus", description=text, required=True)],
            max_turns=max_turns_override or 12,
            tone="supportive",
        )
    policies = raw.get("policies", {})
    if "max_turns" in policies and "max_turns" not in raw:
        raw["max_turns"] = policies.get("max_turns")
    if "tone" in policies and "tone" not in raw:
        raw["tone"] = policies.get("tone")
    if max_turns_override:
        raw["max_turns"] = max_turns_override
    return AgendaFile.model_validate(raw)


def build_graph(config: RunConfig, model: ChatOpenAI) -> StateGraph:
    graph = StateGraph(dict)

    def node_load_context(state: dict) -> dict:
        agenda = load_agenda(config.agenda_path, config.agenda_text, config.max_turns)
        student = load_profile(config.profile_path, config.student_id)
        notes = load_notes(student.student_id)
        snippets = merge_snippets(
            load_recent_summaries(student.student_id),
            load_submissions(config.submissions),
        )
        session = SessionState.initialize(
            agenda=agenda,
            student=student,
            memory_snippets=snippets,
            notes=notes,
            session_id=str(uuid4()),
            output_dir=config.output_dir,
        )
        state["session"] = session
        state["student_reply"] = None
        state["last_question"] = None
        return state

    def node_plan_turn(state: dict) -> dict:
        session: SessionState = state["session"]
        if session.stop_reason:
            return state
        # If agenda is already met, skip model call and move to synthesis.
        if not session.required_atoms_remaining():
            decision = PlanDecision(action=PlanAction.SYNTHESIZE, reason="All required agenda atoms met.")
            session.last_plan = decision
            session.conversation_phase = ConversationPhase.SYNTHESIS
            state["session"] = session
            return state
        # If student recently stalled repeatedly, move to synthesis wrap-up.
        last_student = last_student_turn_text(session)
        if last_student and reply_signals_exit(last_student):
            session.stop_reason = StopReason.STUDENT_EXIT
            session.conversation_phase = ConversationPhase.FINALIZE
            state["session"] = session
            return state
        agenda_atoms_summary = [
            f"{atom.id}:{session.agenda_statuses.get(atom.id, AgendaStatus.UNKNOWN).value}"
            for atom in session.agenda.agenda_atoms
        ]
        transcript_tail = "\n".join(f"{t.speaker}: {t.text}" for t in session.transcript[-6:])
        prompt = render(
            PROMPTS["planner"],
            {
                "topic": session.agenda.topic,
                "agenda_atoms": agenda_atoms_summary,
                "transcript_tail": transcript_tail or "(none)",
                "open_issues": session.open_issues,
                "stall_counts": session.stall_counts,
                "max_turns": session.agenda.max_turns,
                "turn_index": session.turn_index,
            },
        )
        result = call_json(model, PROMPTS["system"], prompt)
        try:
            action_value = PlanAction(result.get("action", "ask_agenda"))
        except Exception:
            action_value = PlanAction.ASK_AGENDA
        decision = PlanDecision(
            action=action_value,
            target_atom_id=result.get("target_atom_id"),
            reason=result.get("reason", ""),
            needs_scaffold=bool(result.get("needs_scaffold", False)),
            stop_signal=bool(result.get("stop_signal", False)),
        )
        if decision.target_atom_id is None and decision.action in {PlanAction.ASK_AGENDA, PlanAction.SCAFFOLD}:
            unmet = session.required_atoms_remaining()
            decision.target_atom_id = unmet[0] if unmet else None
        # Pivot automatically if stalled twice on the same atom
        if (
            decision.target_atom_id
            and session.stall_counts.get(decision.target_atom_id, 0) >= 2
            and decision.action in {PlanAction.ASK_AGENDA, PlanAction.SCAFFOLD}
        ):
            alternative = [
                atom.id
                for atom in session.agenda.agenda_atoms
                if atom.id != decision.target_atom_id
                and session.agenda_statuses.get(atom.id, AgendaStatus.UNKNOWN) != AgendaStatus.MET
            ]
            if alternative:
                decision.action = PlanAction.PIVOT_TOPIC
                decision.target_atom_id = alternative[0]
                decision.reason = decision.reason or "Auto-pivot after repeated stalls."
            else:
                decision.action = PlanAction.SYNTHESIZE
                decision.reason = decision.reason or "Stalled twice; move to synthesis."
        if last_student and reply_signals_stall(last_student) and session.stall_counts.get(decision.target_atom_id or "", 0) >= 2:
            decision.action = PlanAction.SYNTHESIZE
            decision.reason = decision.reason or "Student indicated stall; moving to synthesis."
        if decision.stop_signal:
            session.stop_reason = StopReason.STUDENT_EXIT
        session.last_plan = decision
        if decision.action == PlanAction.SYNTHESIZE:
            session.conversation_phase = ConversationPhase.SYNTHESIS
        elif decision.action == PlanAction.STOP_NOW:
            session.conversation_phase = ConversationPhase.FINALIZE
        else:
            session.conversation_phase = ConversationPhase.PROBING
        state["session"] = session
        return state

    def node_generate_question(state: dict) -> dict:
        session: SessionState = state["session"]
        if session.stop_reason or session.last_plan is None:
            return state
        if session.last_plan.action == PlanAction.STOP_NOW:
            return state
        agenda_focus = agenda_focus_text(session, session.last_plan.target_atom_id)
        transcript_tail = "\n".join(f"{t.speaker}: {t.text}" for t in session.transcript[-4:])
        memory_snippets = "; ".join(snippet.text for snippet in session.memory_snippets[:3])
        prompt = render(
            PROMPTS["question"],
            {
                "topic": session.agenda.topic,
                "student_name": session.student.display_name,
                "tone": session.agenda.tone,
                "agenda_focus": agenda_focus,
                "memory_snippets": memory_snippets or "(none)",
                "notes": "; ".join(session.notes) or "(none)",
                "transcript_tail": transcript_tail or "(none)",
                "needs_scaffold": session.last_plan.needs_scaffold,
            },
        )
        question_text = call_text(model, PROMPTS["system"], prompt)
        question_id = f"{session.last_plan.action.value}_{session.last_plan.target_atom_id or 'synthesis'}_{len(session.transcript)+1}"
        session.transcript.append(
            Turn(speaker="assistant", text=question_text, question_id=question_id)
        )
        state["last_question"] = question_text
        config.console.print(f"[cyan]Tutor:[/cyan] {question_text}")
        state["session"] = session
        return state

    def node_await_reply(state: dict) -> dict:
        session: SessionState = state["session"]
        if session.stop_reason:
            return state
        try:
            reply = config.input_func("Student> ")
        except EOFError:
            session.stop_reason = StopReason.STUDENT_EXIT
            state["session"] = session
            return state
        except KeyboardInterrupt:
            session.stop_reason = StopReason.INTERRUPT
            state["session"] = session
            return state
        state["student_reply"] = reply
        return state

    def node_evaluate_reply(state: dict) -> dict:
        session: SessionState = state["session"]
        reply: str | None = state.get("student_reply")
        if reply is None:
            return state
        if reply_signals_exit(reply):
            session.stop_reason = StopReason.STUDENT_EXIT
            session.transcript.append(Turn(speaker="student", text=reply))
            state["session"] = session
            return state
        if reply_signals_stall(reply) and session.last_plan and session.stall_counts.get(session.last_plan.target_atom_id or "", 0) >= 2:
            session.stop_reason = StopReason.STUDENT_EXIT
            session.transcript.append(Turn(speaker="student", text=reply))
            state["session"] = session
            return state
        # Record student turn
        session.transcript.append(
            Turn(
                speaker="student",
                text=reply,
                question_id=session.transcript[-1].question_id if session.transcript else None,
            )
        )
        session.turn_index += 1
        agenda_atoms_text = "; ".join(f"{atom.id}:{atom.description}" for atom in session.agenda.agenda_atoms)
        eval_prompt = render(
            PROMPTS["evaluator"],
            {
                "question": state.get("last_question", ""),
                "student_reply": reply,
                "agenda_atoms": agenda_atoms_text,
            },
        )
        raw = call_json(model, PROMPTS["system"], eval_prompt)
        updates = []
        for item in raw.get("agenda_updates", []):
            try:
                updates.append(
                    AgendaUpdate(
                        atom_id=item.get("atom_id"),
                        status=AgendaStatus(item.get("status", "unknown")),
                        missing=item.get("missing", []),
                    )
                )
            except Exception:
                continue
        eval_result = EvalResult(
            agenda_updates=updates,
            stop_signal=bool(raw.get("stop_signal", False)),
            open_issues=raw.get("open_issues", []),
        )
        for update in eval_result.agenda_updates:
            prev = session.agenda_statuses.get(update.atom_id, AgendaStatus.UNKNOWN)
            session.agenda_statuses[update.atom_id] = update.status
            if update.status != AgendaStatus.MET and session.last_plan and update.atom_id == session.last_plan.target_atom_id:
                session.stall_counts[update.atom_id] = session.stall_counts.get(update.atom_id, 0) + 1
            elif update.status == AgendaStatus.MET:
                session.stall_counts[update.atom_id] = 0
        session.open_issues = eval_result.open_issues
        if eval_result.stop_signal:
            session.stop_reason = StopReason.STUDENT_EXIT
        state["session"] = session
        return state

    def node_decide_stop(state: dict) -> dict:
        session: SessionState = state["session"]
        if session.stop_reason:
            session.conversation_phase = ConversationPhase.FINALIZE
            state["session"] = session
            return state
        if session.turn_index >= session.agenda.max_turns:
            session.stop_reason = StopReason.MAX_TURNS
            session.conversation_phase = ConversationPhase.FINALIZE
            state["session"] = session
            return state
        remaining = session.required_atoms_remaining()
        if not remaining:
            if session.last_plan and session.last_plan.action == PlanAction.SYNTHESIZE:
                session.stop_reason = StopReason.COMPLETED
                session.conversation_phase = ConversationPhase.FINALIZE
            else:
                session.conversation_phase = ConversationPhase.SYNTHESIS
        elif session.conversation_phase == ConversationPhase.SYNTHESIS and session.last_plan and session.last_plan.action == PlanAction.SYNTHESIZE:
            session.stop_reason = StopReason.COMPLETED
            session.conversation_phase = ConversationPhase.FINALIZE
        state["session"] = session
        return state

    def node_summarize_and_persist(state: dict) -> dict:
        session: SessionState = state["session"]
        if session.summary:
            return state
        transcript_text = "\n".join(f"{t.speaker}: {t.text}" for t in session.transcript)
        agenda_desc = "; ".join(
            f"{atom.id}:{session.agenda_statuses.get(atom.id, AgendaStatus.UNKNOWN).value}"
            for atom in session.agenda.agenda_atoms
        )
        summary_prompt = render(
            PROMPTS["summary"],
            {
                "topic": session.agenda.topic,
                "agenda_atoms": agenda_desc,
                "transcript": transcript_text,
                "open_issues": session.open_issues,
                "notes": session.notes,
            },
        )
        summary = call_json(model, PROMPTS["system"], summary_prompt)
        session.summary = summary
        if session.stop_reason is None:
            session.stop_reason = StopReason.COMPLETED
        persist_run(session)
        config.console.print(f"[green]Saved artifacts:[/green] {session.output_dir or ''}")
        config.console.print(f"[bold]Stop reason:[/bold] {session.stop_reason.value}")
        state["session"] = session
        return state

    graph.add_node("load_context", node_load_context)
    graph.add_node("plan_turn", node_plan_turn)
    graph.add_node("generate_question", node_generate_question)
    graph.add_node("await_reply", node_await_reply)
    graph.add_node("evaluate_reply", node_evaluate_reply)
    graph.add_node("decide_stop", node_decide_stop)
    graph.add_node("summarize_and_persist", node_summarize_and_persist)

    graph.add_edge(START, "load_context")
    graph.add_edge("load_context", "plan_turn")
    graph.add_conditional_edges(
        "plan_turn",
        lambda s: (
            "summarize_and_persist"
            if s["session"].last_plan and s["session"].last_plan.action == PlanAction.STOP_NOW
            else "generate_question"
        ),
        {
            "generate_question": "generate_question",
            "summarize_and_persist": "summarize_and_persist",
        },
    )
    graph.add_edge("generate_question", "await_reply")
    graph.add_edge("await_reply", "evaluate_reply")
    graph.add_edge("evaluate_reply", "decide_stop")
    graph.add_conditional_edges(
        "decide_stop",
        lambda s: "summarize_and_persist" if s["session"].conversation_phase == ConversationPhase.FINALIZE else "plan_turn",
        {
            "summarize_and_persist": "summarize_and_persist",
            "plan_turn": "plan_turn",
        },
    )
    graph.add_edge("summarize_and_persist", END)
    return graph.compile()


def run_session(
    agenda_path: Path | None,
    agenda_text: str | None,
    student_id: str,
    profile_path: Path | None,
    submissions: list[Path],
    max_turns: int | None,
    model_name: str,
    output_dir: Path | None,
    console: Console | None = None,
    input_func: Callable[[str], str] | None = None,
) -> SessionState:
    console = console or Console()
    input_func = input_func or input
    chat_model = ChatOpenAI(model=model_name, temperature=0.2)
    config = RunConfig(
        agenda_path=agenda_path,
        agenda_text=agenda_text,
        student_id=student_id,
        profile_path=profile_path,
        submissions=submissions,
        max_turns=max_turns,
        model=model_name,
        output_dir=output_dir,
        input_func=input_func,
        console=console,
    )
    compiled = build_graph(config, chat_model)
    result_state = compiled.invoke({})
    session: SessionState = result_state["session"]
    return session
