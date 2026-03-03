from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from guided_reflection_cli.settings import Settings
from test_support import workspace_temp_dir


class SettingsTests(unittest.TestCase):
    def test_from_env_prefers_explicit_dotenv_over_inherited_process_values(self) -> None:
        with workspace_temp_dir() as temp_dir:
            env_path = temp_dir / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "LLM_PROVIDER=openai",
                        "OPENAI_API_KEY=file-key-12345",
                        "OPENAI_MODEL=gpt-4o-mini",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "LLM_PROVIDER": "fake",
                    "OPENAI_API_KEY": "process-key-98765",
                },
                clear=False,
            ):
                settings = Settings.from_env(env_path=env_path)

            self.assertEqual(settings.llm_provider, "fake")
            self.assertEqual(settings.openai_api_key, "file-key-12345")
            self.assertEqual(settings.openai_model, "gpt-4o-mini")

    def test_from_env_still_allows_process_provider_override(self) -> None:
        with workspace_temp_dir() as temp_dir:
            env_path = temp_dir / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "LLM_PROVIDER=openai",
                        "OPENAI_API_KEY=file-key-12345",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "LLM_PROVIDER": "fake",
                    "OPENAI_API_KEY": "process-key-98765",
                },
                clear=False,
            ):
                settings = Settings.from_env(env_path=env_path)

            self.assertEqual(settings.llm_provider, "fake")
            self.assertEqual(settings.openai_api_key, "file-key-12345")
