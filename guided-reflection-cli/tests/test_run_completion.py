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
