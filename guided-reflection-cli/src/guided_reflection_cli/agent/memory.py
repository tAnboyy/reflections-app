"""File-backed student memory store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import yaml

from guided_reflection_cli.agent.state import MemorySnippet, StudentProfile

DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
STUDENTS_ROOT = DATA_ROOT / "students"
RUNS_ROOT = DATA_ROOT / "runs"


def ensure_roots() -> None:
    STUDENTS_ROOT.mkdir(parents=True, exist_ok=True)
    RUNS_ROOT.mkdir(parents=True, exist_ok=True)


def student_dir(student_id: str) -> Path:
    ensure_roots()
    return STUDENTS_ROOT / student_id


def load_profile(profile_path: Path | None, student_id: str) -> StudentProfile:
    if profile_path and profile_path.exists():
        raw = yaml.safe_load(profile_path.read_text(encoding="utf-8")) or {}
    else:
        raw = {"student_id": student_id}
    raw.setdefault("student_id", student_id)
    return StudentProfile.model_validate(raw)


def load_notes(student_id: str) -> list[str]:
    path = student_dir(student_id) / "notes.md"
    if not path.exists():
        return []
    return [line.strip("- ").strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_notes(student_id: str, bullets: Iterable[str]) -> None:
    bullets = [b for b in bullets if b.strip()]
    if not bullets:
        return
    path = student_dir(student_id) / "notes.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        for bullet in bullets:
            fh.write(f"- {bullet.strip()}\n")


def load_history(student_id: str) -> list[dict]:
    path = student_dir(student_id) / "history.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []


def save_history(student_id: str, history: list[dict]) -> None:
    path = student_dir(student_id) / "history.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(history, indent=2), encoding="utf-8")


def load_recent_summaries(student_id: str, limit: int = 3) -> list[MemorySnippet]:
    history = load_history(student_id)[-limit:]
    snippets: list[MemorySnippet] = []
    for item in history:
        summary = item.get("summary", "")
        if summary:
            snippets.append(
                MemorySnippet(
                    snippet_id=item.get("run_id", ""),
                    text=summary,
                    source="history",
                )
            )
    return snippets


TEXT_EXTS = {".txt", ".md", ".markdown", ".json"}


def read_submission(path: Path) -> str:
    if path.suffix.lower() == ".json":
        try:
            return json.dumps(json.loads(path.read_text(encoding="utf-8")), indent=2)[:2000]
        except Exception:
            return path.read_text(encoding="utf-8")[:2000]
    return path.read_text(encoding="utf-8")[:2000]


def load_submissions(paths: list[Path] | None) -> list[MemorySnippet]:
    snippets: list[MemorySnippet] = []
    for path in paths or []:
        if not path.exists():
            continue
        if path.suffix.lower() not in TEXT_EXTS:
            continue
        try:
            text = read_submission(path)
        except Exception:
            continue
        snippets.append(MemorySnippet(snippet_id=path.stem, text=text, source="submission"))
    return snippets


def merge_snippets(*groups: list[MemorySnippet]) -> list[MemorySnippet]:
    merged: list[MemorySnippet] = []
    seen = set()
    for group in groups:
        for item in group:
            if item.snippet_id in seen:
                continue
            seen.add(item.snippet_id)
            merged.append(item)
    return merged
