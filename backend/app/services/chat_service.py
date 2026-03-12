"""Chat service — manages in-memory session state and LLM calls."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from app.services.llm import LLMProvider
from app.services.prompts import build_reflection_prompt


@dataclass
class Session:
    session_id: str
    student_id: str
    module_id: str
    config: dict
    messages: list[dict] = field(default_factory=list)


# In-memory store — good enough for a single-process prototype.
_sessions: dict[str, Session] = {}


def start_session(
    student_id: str,
    module_id: str,
    config: dict,
    llm: LLMProvider,
) -> tuple[str, str]:
    """Create a new chat session and return (session_id, greeting)."""
    session_id = str(uuid.uuid4())
    system_prompt = build_reflection_prompt(config)
    messages = [{"role": "system", "content": system_prompt}]

    # Generate an opening greeting
    greeting = llm.generate(messages)
    messages.append({"role": "assistant", "content": greeting})

    _sessions[session_id] = Session(
        session_id=session_id,
        student_id=student_id,
        module_id=module_id,
        config=config,
        messages=messages,
    )
    return session_id, greeting


def send_message(session_id: str, user_msg: str, llm: LLMProvider, time_remaining: int = 600) -> str:
    """Append user message, call LLM, return assistant reply."""
    session = _sessions.get(session_id)
    if session is None:
        raise KeyError(f"Session {session_id} not found")

    content = user_msg
    if time_remaining <= 120:
        mins = time_remaining // 60
        secs = time_remaining % 60
        time_str = f"{mins}:{secs:02d}"
        content = f"[{time_str} remaining] {user_msg}"

    session.messages.append({"role": "user", "content": content})
    reply = llm.generate(session.messages)
    session.messages.append({"role": "assistant", "content": reply})
    return reply


def end_session(session_id: str) -> Session:
    """Pop and return the completed session."""
    session = _sessions.pop(session_id, None)
    if session is None:
        raise KeyError(f"Session {session_id} not found")
    return session


def format_transcript(messages: list[dict]) -> str:
    """Convert message list into a readable transcript string."""
    lines = []
    for msg in messages:
        role = msg["role"].upper()
        if role == "SYSTEM":
            continue
        lines.append(f"{role}: {msg['content']}")
    return "\n\n".join(lines)
