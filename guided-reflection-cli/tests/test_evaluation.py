from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from guided_reflection_cli.evaluation import apply_turn_evaluation, evaluate_pending_reply
from guided_reflection_cli.graph import GuidedReflectionGraph
from guided_reflection_cli.llm import FakeReflectionLLM
from guided_reflection_cli.template_loader import load_student_profile, load_template
from guided_reflection_cli.schemas import AgendaStatus, RequiredQuestionStatus


FIXTURES = Path(__file__).resolve().parents[1] / "examples"


class EvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        template = load_template(FIXTURES / "templates" / "critical_reflection_example.yaml")
        student = load_student_profile(FIXTURES / "students" / "student_example.yaml")
        graph = GuidedReflectionGraph(FakeReflectionLLM())
        self.state = graph.initialize_session(template, student)
        self.state = graph.step(self.state)

    def test_required_question_becomes_acceptable_when_evidence_is_sufficient(self) -> None:
        self.state.pending_student_reply = (
            "The problem in my project is understanding why flight delays spike during certain months, "
            "and my main question is which weather and scheduling patterns best explain the worst delays "
            "in the dataset."
        )
        evaluation = evaluate_pending_reply(self.state)
        self.assertEqual(evaluation.question_status, RequiredQuestionStatus.ACCEPTABLE)
        self.assertEqual(evaluation.agenda_atom_updates[0].status, AgendaStatus.MET)

    def test_vague_answer_leaves_atom_partially_met(self) -> None:
        self.state.pending_student_reply = "I am not sure about the problem yet."
        evaluation = evaluate_pending_reply(self.state)
        self.assertEqual(evaluation.question_status, RequiredQuestionStatus.ASKED_UNACCEPTABLE)
        updated_state = apply_turn_evaluation(self.state, evaluation)
        self.assertEqual(updated_state.agenda_atom_statuses["problem_definition"], AgendaStatus.PARTIALLY_MET)


class AgendaFirstEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        template = load_template(FIXTURES / "templates" / "new_template.yaml")
        student = load_student_profile(FIXTURES / "students" / "student_example.yaml")
        graph = GuidedReflectionGraph(FakeReflectionLLM())
        self.state = graph.initialize_session(template, student)
        self.state = graph.step(self.state)

    def test_vague_answer_is_recorded_without_triggering_required_question_retry(self) -> None:
        self.state.pending_student_reply = "I am not sure yet."
        evaluation = evaluate_pending_reply(self.state)
        self.assertEqual(evaluation.question_status, RequiredQuestionStatus.ACCEPTABLE)
        self.assertEqual(evaluation.agenda_atom_updates[0].status, AgendaStatus.PARTIALLY_MET)
        updated_state = apply_turn_evaluation(self.state, evaluation)
        self.assertEqual(updated_state.agenda_atom_statuses["claim"], AgendaStatus.PARTIALLY_MET)
        self.assertTrue(updated_state.agenda_atom_missing["claim"])
