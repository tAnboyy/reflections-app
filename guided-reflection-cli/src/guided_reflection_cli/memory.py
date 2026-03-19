"""Memory provider interfaces for future retrieval integrations."""

from __future__ import annotations

from typing import Protocol

from guided_reflection_cli.schemas import MemorySnippet


class MemoryProvider(Protocol):
    """Protocol for future retrieval-backed personalization."""

    def retrieve(self, student_id: str, query: str, limit: int = 5) -> list[MemorySnippet]:
        ...


class NullMemoryProvider:
    """MVP memory provider that returns no retrieval snippets."""

    def retrieve(self, student_id: str, query: str, limit: int = 5) -> list[MemorySnippet]:
        _ = (student_id, query, limit)
        return []
