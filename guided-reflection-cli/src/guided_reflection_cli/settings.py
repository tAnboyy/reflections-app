"""Environment-backed settings for the guided reflection CLI."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


def _default_env_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"


def _load_env_file(env_path: str | Path | None = None) -> dict[str, str]:
    dotenv_path = Path(env_path) if env_path is not None else _default_env_path()
    raw_values = dotenv_values(dotenv_path)
    return {
        key: value.strip()
        for key, value in raw_values.items()
        if isinstance(key, str) and isinstance(value, str)
    }


@dataclass(slots=True)
class Settings:
    """Runtime settings for model-backed features."""

    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    @classmethod
    def from_env(cls, env_path: str | Path | None = None) -> "Settings":
        env_file_values = _load_env_file(env_path)
        return cls(
            llm_provider=(
                os.getenv("LLM_PROVIDER")
                or env_file_values.get("LLM_PROVIDER")
                or "openai"
            ).strip().lower(),
            # Prefer the CLI-local .env for API keys so an unrelated shell export
            # from another project does not silently hijack requests.
            openai_api_key=(
                env_file_values.get("OPENAI_API_KEY")
                or os.getenv("OPENAI_API_KEY")
                or ""
            ).strip(),
            openai_model=(
                os.getenv("OPENAI_MODEL")
                or env_file_values.get("OPENAI_MODEL")
                or "gpt-4o-mini"
            ).strip(),
            ollama_base_url=(
                os.getenv("OLLAMA_BASE_URL")
                or env_file_values.get("OLLAMA_BASE_URL")
                or "http://localhost:11434"
            ).strip(),
            ollama_model=(
                os.getenv("OLLAMA_MODEL")
                or env_file_values.get("OLLAMA_MODEL")
                or "llama3.1"
            ).strip(),
        )

    def validate_provider_requirements(self) -> None:
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is required when LLM_PROVIDER is set to 'openai'. "
                "Use LLM_PROVIDER=fake for offline runs."
            )
        if self.llm_provider == "ollama":
            raise RuntimeError(
                "LLM_PROVIDER='ollama' is reserved for a future provider implementation. "
                "Use 'openai' or 'fake' for now."
            )
