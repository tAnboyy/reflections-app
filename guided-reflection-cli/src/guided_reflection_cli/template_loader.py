"""YAML loading, template validation, and starter template creation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from guided_reflection_cli.schemas import ReflectionTemplate, StudentProfile


STARTER_TEMPLATE = """# Guided reflection template
template_id: ethics-reflection-week-4
version: 1
title: Ethical Tradeoffs in Product Design
topic: Product ethics
assignment:
  statement: >
    Reflect on a product decision that balances business goals and user trust.
  deliverable: Short guided reflection
agenda_atoms:
  - id: claim
    description: Student states a clear position on the tradeoff.
    required: true
    acceptance_rules:
      min_words: 20
      must_include_concrete_position: true
    linked_rubric_criteria: [clarity]
  - id: example
    description: Student gives a specific example from experience or coursework.
    required: true
    acceptance_rules:
      must_include_example: true
    linked_rubric_criteria: [evidence]
question_bank:
  - id: opening_position
    prompt: What is your current position on this tradeoff?
    required: true
    intent_tags: [warmup, claim]
    linked_atoms: [claim]
  - id: concrete_example
    prompt: Can you describe a specific case that shaped your thinking?
    required: true
    intent_tags: [probe, evidence]
    linked_atoms: [example]
rubric:
  - id: clarity
    description: Response is specific and understandable.
    scale_min: 0
    scale_max: 3
  - id: evidence
    description: Response uses a concrete, relevant example.
    scale_min: 0
    scale_max: 3
policies:
  tone: supportive
  max_turns: 12
  min_student_words_per_turn: 15
  allow_scaffolding: true
  completion_mode: required_atoms_and_required_questions
  final_summary_style: concise
"""


def write_starter_template(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(STARTER_TEMPLATE, encoding="utf-8")
    return output_path


def load_template(path: str | Path) -> ReflectionTemplate:
    return ReflectionTemplate.model_validate(_load_yaml(path))


def load_student_profile(path: str | Path) -> StudentProfile:
    return StudentProfile.model_validate(_load_yaml(path))


def validate_template(path: str | Path) -> tuple[bool, str]:
    try:
        load_template(path)
    except ValidationError as exc:
        return False, format_validation_error(exc)
    except Exception as exc:  # pragma: no cover - defensive wrapper
        return False, str(exc)
    return True, "Template is valid."


def _load_yaml(path: str | Path) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    content = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    if not isinstance(content, dict):
        raise ValueError(f"{file_path} must contain a YAML mapping at the top level")
    return content


def format_validation_error(exc: ValidationError) -> str:
    lines = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", [])) or "<root>"
        lines.append(f"{location}: {error.get('msg', 'validation error')}")
    return "\n".join(lines)
