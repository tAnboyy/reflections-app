from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from guided_reflection_cli.evaluation import plan_next_step
from guided_reflection_cli.graph import GuidedReflectionGraph
from guided_reflection_cli.llm import FakeReflectionLLM
from guided_reflection_cli.template_loader import load_student_profile, load_template
from guided_reflection_cli.schemas import RequiredQuestionStatus


FIXTURES = Path(__file__).resolve().parents[1] / "examples"


class PlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        template = load_template(FIXTURES / "templates" / "critical_reflection_example.yaml")
        student = load_student_profile(FIXTURES / "students" / "student_example.yaml")
        graph = GuidedReflectionGraph(FakeReflectionLLM())
        self.state = graph.initialize_session(template, student)

    def test_planner_prioritizes_unmet_required_question_over_optional_question(self) -> None:
        plan = plan_next_step(self.state)
        self.assertEqual(plan.target_question_id, "project_problem")
        self.assertIn("problem_definition", plan.target_atom_ids)

    def test_planner_switches_to_scaffold_after_repeated_unacceptable_answers(self) -> None:
        self.state.required_question_statuses["project_problem"] = RequiredQuestionStatus.ASKED_UNACCEPTABLE
        self.state.question_unacceptable_counts["project_problem"] = 2
        plan = plan_next_step(self.state)
        self.assertEqual(plan.target_question_id, "project_problem")
        self.assertEqual(plan.strategy.value, "scaffold")
        self.assertTrue(plan.needs_scaffolding)
