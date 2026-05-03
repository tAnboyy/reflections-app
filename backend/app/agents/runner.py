"""Runner — compile graphs with PostgreSQL checkpointer, expose invoke helpers."""

from __future__ import annotations

from langgraph.checkpoint.postgres import PostgresSaver

from app.agents.graphs.init_graph import build_init_graph
from app.agents.graphs.message_graph import build_message_graph
from app.agents.graphs.end_graph import build_end_graph
from app.database import DATABASE_URL

_checkpointer: PostgresSaver | None = None
_init_graph = None
_message_graph = None
_end_graph = None


def setup_checkpointer() -> None:
    """Create checkpoint tables and compile graphs. Called once at app startup."""
    global _checkpointer, _init_graph, _message_graph, _end_graph

    # PostgresSaver expects a plain postgresql:// URL (not the +psycopg SQLAlchemy variant)
    sync_url = DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")

    _checkpointer = PostgresSaver.from_conn_string(sync_url)
    _checkpointer.setup()

    _init_graph = build_init_graph().compile(checkpointer=_checkpointer)
    _message_graph = build_message_graph().compile(checkpointer=_checkpointer)
    _end_graph = build_end_graph().compile(checkpointer=_checkpointer)


def _thread_config(session_id: str, db=None) -> dict:
    cfg: dict = {"configurable": {"thread_id": session_id}}
    if db is not None:
        cfg["db"] = db
    return cfg


def invoke_start(session_id: str, student_id: str, module_id: str, db) -> dict:
    return _init_graph.invoke(
        {
            "session_id": session_id,
            "student_id": student_id,
            "module_id": module_id,
        },
        config=_thread_config(session_id, db),
    )


def invoke_message(session_id: str, user_message: str) -> dict:
    return _message_graph.invoke(
        {"user_message": user_message},
        config=_thread_config(session_id),
    )


def invoke_end(session_id: str, db) -> dict:
    return _end_graph.invoke(
        {},
        config=_thread_config(session_id, db),
    )
