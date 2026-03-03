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
from guided_reflection_cli.schemas import PromptSource, TurnPurpose
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

    def test_legacy_generated_question_drops_old_command_like_suffix(self) -> None:
        state = GuidedReflectionGraph(FakeReflectionLLM()).step(self.state)
        self.assertNotIn("Be specific and concrete.", state.last_assistant_question.question_text)
        self.assertNotIn("Answer in 2-3 sentences.", state.last_assistant_question.question_text)


class AgendaFirstPlannerTests(unittest.TestCase):
    def setUp(self) -> None:
        template = load_template(FIXTURES / "templates" / "new_template.yaml")
        student = load_student_profile(FIXTURES / "students" / "student_example.yaml")
        self.graph = GuidedReflectionGraph(FakeReflectionLLM())
        self.state = self.graph.initialize_session(template, student)

    def test_planner_asks_first_required_agenda_atom_in_template_order(self) -> None:
        plan = plan_next_step(self.state)
        self.assertIsNone(plan.target_question_id)
        self.assertEqual(plan.target_atom_ids, ["claim"])
        self.assertEqual(plan.prompt_source, PromptSource.AGENDA_ATOM)
        self.assertEqual(plan.turn_purpose, TurnPurpose.OPENING)

    def test_soft_capture_moves_to_next_atom_after_incomplete_answer(self) -> None:
        self.state = self.graph.step(self.state)
        self.state.pending_student_reply = "I am not sure yet."
        self.state = self.graph.step(self.state)
        next_plan = plan_next_step(self.state)
        self.assertEqual(next_plan.target_atom_ids, ["example"])
        self.assertEqual(next_plan.turn_purpose, TurnPurpose.OPENING)

    def test_planner_schedules_one_synthesis_turn_after_first_pass(self) -> None:
        self.state = self.graph.step(self.state)
        self.state.pending_student_reply = (
            "I think the tradeoff should favor user trust because short-term business wins are not worth long-term "
            "damage."
        )
        self.state = self.graph.step(self.state)
        self.state = self.graph.step(self.state)
        self.state.pending_student_reply = (
            "For example, in class we discussed a product that pushed aggressive tracking and lost user confidence."
        )
        self.state = self.graph.step(self.state)
        plan = plan_next_step(self.state)
        self.assertEqual(plan.prompt_source, PromptSource.SYSTEM_SYNTHESIS)
        self.assertEqual(plan.turn_purpose, TurnPurpose.SYNTHESIS)

    def test_agenda_first_question_uses_gentle_opening_template(self) -> None:
        self.state = self.graph.step(self.state)
        self.assertIn("Let's start with", self.state.last_assistant_question.question_text)
        self.assertNotIn("Be specific and concrete.", self.state.last_assistant_question.question_text)
