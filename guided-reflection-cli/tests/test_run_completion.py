from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

from rich.console import Console

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from guided_reflection_cli.session_runner import run_interactive_session
from guided_reflection_cli.schemas import StopReason
from test_support import workspace_temp_dir


FIXTURES = Path(__file__).resolve().parents[1] / "examples"


class RunCompletionTests(unittest.TestCase):
    def setUp(self) -> None:
        os.environ["LLM_PROVIDER"] = "fake"
        self.template_path = FIXTURES / "templates" / "critical_reflection_example.yaml"
        self.student_path = FIXTURES / "students" / "student_example.yaml"
        self.agenda_first_template_path = FIXTURES / "templates" / "new_template.yaml"

    def test_run_stops_when_requirements_met_and_writes_artifacts(self) -> None:
        answers = iter(
            [
                (
                    "The problem in my project is figuring out why airline delays spike during certain "
                    "months, and my main question is which weather and scheduling patterns best explain "
                    "the longest delays in the dataset."
                ),
                (
                    "I found the dataset on Kaggle as my source, and the dataset tracks U.S. flights with "
                    "delay details. One feature I care about is departure delay because it connects directly "
                    "to the timing patterns I want to compare."
                ),
                (
                    "My preprocessing step is converting dates, removing duplicate rows, and filling a few "
                    "missing weather values. I call this preprocessing because the raw data is messy and I "
                    "need consistent fields before plotting trends."
                ),
                (
                    "My main visualization is a monthly line chart with a companion bar chart by airline. "
                    "This visualization gives an insight into seasonal peaks and helps me compare which "
                    "carriers contribute most to the highest delay periods."
                ),
                (
                    "I learned that holiday-season delays rise earlier than I expected, and the analysis "
                    "helps answer my original question about when delays become most severe. It also shows "
                    "that schedule pressure matters more than a single carrier."
                ),
                (
                    "A misleading chart could cause harm if readers blame one airline without context, and "
                    "the dataset is missing passenger experience, cancellations, and local airport staffing "
                    "details. Those missing perspectives limit how fair my conclusion can be."
                ),
                (
                    "My references will include the dataset source link, the Kaggle page, and the pandas "
                    "documentation I used while cleaning dates. Listing each reference makes the write-up "
                    "easier to verify."
                ),
                (
                    "I will share a link to the full code notebook in my GitHub repository so reviewers can "
                    "inspect every chart and preprocessing step. The code section will point directly to "
                    "that notebook link."
                ),
            ]
        )

        with workspace_temp_dir() as temp_dir:
            run_dir, state = run_interactive_session(
                template_path=self.template_path,
                student_path=self.student_path,
                output_dir=temp_dir,
                console=Console(record=True),
                input_func=lambda _: next(answers),
            )

            self.assertEqual(state.stop_reason, StopReason.COMPLETED)
            self.assertTrue((run_dir / "result.json").exists())
            self.assertTrue((run_dir / "report.md").exists())
            self.assertTrue((run_dir / "transcript.md").exists())

    def test_run_finalizes_partial_output_on_max_turns(self) -> None:
        answers = iter(["I am not sure."])

        with workspace_temp_dir() as temp_dir:
            run_dir, state = run_interactive_session(
                template_path=self.template_path,
                student_path=self.student_path,
                output_dir=temp_dir,
                max_turns=1,
                console=Console(record=True),
                input_func=lambda _: next(answers),
            )

            self.assertEqual(state.stop_reason, StopReason.MAX_TURNS)
            self.assertTrue((run_dir / "result.json").exists())

    def test_run_finalizes_partial_output_on_max_questions(self) -> None:
        answers = iter(
            [
                (
                    "The problem in my project is understanding why customer churn increases after price "
                    "changes, and my main question is which features best explain that pattern."
                ),
            ]
        )

        with workspace_temp_dir() as temp_dir:
            run_dir, state = run_interactive_session(
                template_path=self.agenda_first_template_path,
                student_path=self.student_path,
                output_dir=temp_dir,
                max_questions=1,
                console=Console(record=True),
                input_func=lambda _: next(answers),
            )

            assistant_turns = [turn for turn in state.transcript if turn.speaker == "assistant"]
            self.assertEqual(state.stop_reason, StopReason.MAX_QUESTIONS)
            self.assertEqual(len(assistant_turns), 1)
            self.assertTrue((run_dir / "result.json").exists())

    def test_run_finalizes_partial_output_on_interrupt(self) -> None:
        def raising_input(_: str) -> str:
            raise KeyboardInterrupt

        with workspace_temp_dir() as temp_dir:
            run_dir, state = run_interactive_session(
                template_path=self.template_path,
                student_path=self.student_path,
                output_dir=temp_dir,
                console=Console(record=True),
                input_func=raising_input,
            )

            self.assertEqual(state.stop_reason, StopReason.INTERRUPT)
            self.assertTrue((run_dir / "report.md").exists())

    def test_run_finalizes_when_student_requests_stop_in_plain_language(self) -> None:
        answers = iter(["Can we stop here? No more questions."])

        with workspace_temp_dir() as temp_dir:
            run_dir, state = run_interactive_session(
                template_path=self.agenda_first_template_path,
                student_path=self.student_path,
                output_dir=temp_dir,
                console=Console(record=True),
                input_func=lambda _: next(answers),
            )

            self.assertEqual(state.stop_reason, StopReason.STUDENT_EXIT)
            self.assertTrue((run_dir / "report.md").exists())

    def test_agenda_first_run_moves_forward_and_finishes_with_synthesis(self) -> None:
        answers = iter(
            [
                "I am still figuring out my exact position on the tradeoff.",
                (
                    "For example, in class we looked at a product that pushed for more tracking, and that case "
                    "made me think trust is harder to rebuild once it slips."
                ),
                (
                    "My main takeaway is that product decisions should protect user trust even when business "
                    "pressure makes the easier option feel tempting."
                ),
            ]
        )

        with workspace_temp_dir() as temp_dir:
            run_dir, state = run_interactive_session(
                template_path=self.agenda_first_template_path,
                student_path=self.student_path,
                output_dir=temp_dir,
                console=Console(record=True),
                input_func=lambda _: next(answers),
            )

            assistant_question_ids = [turn.question_id for turn in state.transcript if turn.speaker == "assistant"]
            self.assertEqual(state.stop_reason, StopReason.COMPLETED)
            self.assertEqual(
                assistant_question_ids,
                ["agenda_claim_opening", "agenda_example_opening", "agenda_synthesis"],
            )
            self.assertEqual(state.final_report.required_question_report, [])
            self.assertTrue((run_dir / "report.md").exists())

    def test_agenda_first_report_surfaces_missing_agenda_elements(self) -> None:
        answers = iter(
            [
                "I am not sure yet.",
                (
                    "For example, during coursework I saw how a privacy decision could affect whether users "
                    "kept trusting the product."
                ),
                "The main takeaway is that the tradeoff needs more careful reasoning than I first assumed.",
            ]
        )

        with workspace_temp_dir() as temp_dir:
            _, state = run_interactive_session(
                template_path=self.agenda_first_template_path,
                student_path=self.student_path,
                output_dir=temp_dir,
                console=Console(record=True),
                input_func=lambda _: next(answers),
            )

            claim_row = next(item for item in state.final_report.agenda_completion_report if item.atom_id == "claim")
            self.assertTrue(claim_row.missing_elements)
            self.assertTrue(any("Follow-up needed on" in note for note in state.final_report.teacher_notes))
