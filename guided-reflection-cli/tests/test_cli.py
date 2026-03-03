from __future__ import annotations

import sys
import unittest
from pathlib import Path

import yaml
from typer.testing import CliRunner

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from guided_reflection_cli.cli import app
from test_support import workspace_temp_dir


class CliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_template_init_creates_file(self) -> None:
        with workspace_temp_dir() as temp_dir:
            output_path = temp_dir / "starter.yaml"
            result = self.runner.invoke(app, ["template", "init", str(output_path)])
            self.assertEqual(result.exit_code, 0, result.stdout)
            self.assertTrue(output_path.exists())
            parsed = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            self.assertEqual(parsed["template_id"], "ethics-reflection-week-4")
            self.assertNotIn("question_bank", parsed)
            self.assertEqual(parsed["policies"]["authoring_mode"], "agenda_first")
            self.assertEqual(parsed["policies"]["completion_mode"], "soft_capture")
            self.assertEqual(parsed["policies"]["max_questions"], 5)

    def test_template_validate_returns_nonzero_on_invalid_file(self) -> None:
        invalid_template = """
template_id: invalid
version: 1
title: Invalid
topic: Test
assignment:
  statement: Test
  deliverable: Test
agenda_atoms: []
question_bank: []
rubric: []
policies:
  authoring_mode: legacy_question_bank
  conversation_style: gentle_coach
  tone: supportive
  max_turns: 0
  min_student_words_per_turn: 1
  allow_scaffolding: true
  completion_mode: required_atoms_and_required_questions
  final_summary_style: concise
"""
        with workspace_temp_dir() as temp_dir:
            template_path = temp_dir / "invalid.yaml"
            template_path.write_text(invalid_template, encoding="utf-8")
            result = self.runner.invoke(app, ["template", "validate", str(template_path)])
            self.assertNotEqual(result.exit_code, 0)
            self.assertIn("max_turns", result.stdout)
