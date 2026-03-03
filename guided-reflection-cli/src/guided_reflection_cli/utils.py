"""Utility helpers shared across the guided reflection CLI."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def contains_any(text: str, phrases: list[str]) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(phrase) in normalized for phrase in phrases)


def slugify(value: str) -> str:
    cleaned = _NON_ALNUM_RE.sub("-", value.strip().lower()).strip("-")
    return cleaned or "item"


def utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def unique_preserving_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
