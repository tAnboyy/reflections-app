from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from guided_reflection_cli.template_loader import validate_template
from test_support import workspace_temp_dir


FIXTURES = Path(__file__).resolve().parents[1] / "examples"


class TemplateValidationTests(unittest.TestCase):
    def test_example_template_is_valid(self) -> None:
        template_path = FIXTURES / "templates" / "critical_reflection_example.yaml"
        is_valid, message = validate_template(template_path)
        self.assertTrue(is_valid, message)

    def test_agenda_first_example_template_is_valid(self) -> None:
        template_path = FIXTURES / "templates" / "new_template.yaml"
        is_valid, message = validate_template(template_path)
        self.assertTrue(is_valid, message)

    def test_duplicate_ids_fail_validation(self) -> None:
        broken_template = """
template_id: duplicate-test
version: 1
title: Duplicate IDs
topic: Test
assignment:
  statement: Test
  deliverable: Test
agenda_atoms:
  - id: claim
    description: First
  - id: claim
    description: Second
rubric: []
policies:
  authoring_mode: agenda_first
  conversation_style: gentle_coach
  tone: supportive
  max_turns: 2
  min_student_words_per_turn: 1
  allow_scaffolding: true
  completion_mode: soft_capture
  final_summary_style: concise
"""
        with workspace_temp_dir() as temp_dir:
            path = temp_dir / "duplicate.yaml"
            path.write_text(broken_template, encoding="utf-8")
            is_valid, message = validate_template(path)
        self.assertFalse(is_valid)
        self.assertIn("duplicate id 'claim'", message)

    def test_broken_links_fail_validation(self) -> None:
        broken_template = """
template_id: broken-links
version: 1
title: Broken Links
topic: Test
assignment:
  statement: Test
  deliverable: Test
agenda_atoms:
  - id: claim
    description: First
    linked_rubric_criteria: [missing_rubric]
question_bank:
  - id: q1
    prompt: Hello?
    required: true
    linked_atoms: [missing_atom]
rubric:
  - id: clarity
    description: Clarity
    scale_min: 0
    scale_max: 3
policies:
  authoring_mode: legacy_question_bank
  conversation_style: gentle_coach
  tone: supportive
  max_turns: 2
  min_student_words_per_turn: 1
  allow_scaffolding: true
  completion_mode: required_atoms_and_required_questions
  final_summary_style: concise
"""
        with workspace_temp_dir() as temp_dir:
            path = temp_dir / "broken.yaml"
            path.write_text(broken_template, encoding="utf-8")
            is_valid, message = validate_template(path)
        self.assertFalse(is_valid)
        self.assertIn("references unknown atom", message)

    def test_agenda_first_template_rejects_question_bank(self) -> None:
        broken_template = """
template_id: agenda-first-with-questions
version: 1
title: Invalid
topic: Test
assignment:
  statement: Test
  deliverable: Test
agenda_atoms:
  - id: claim
    description: a clear claim
question_bank:
  - id: q1
    prompt: Hello?
    required: true
    linked_atoms: [claim]
rubric: []
policies:
  authoring_mode: agenda_first
  conversation_style: gentle_coach
  tone: supportive
  max_turns: 2
  min_student_words_per_turn: 1
  allow_scaffolding: true
  completion_mode: soft_capture
  final_summary_style: concise
"""
        with workspace_temp_dir() as temp_dir:
            path = temp_dir / "agenda-first-invalid.yaml"
            path.write_text(broken_template, encoding="utf-8")
            is_valid, message = validate_template(path)
        self.assertFalse(is_valid)
        self.assertIn("must not define question_bank", message)
