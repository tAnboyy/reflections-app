"""LLM provider abstraction — swap between OpenAI and Ollama via env var."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod

import requests
import json
from openai import OpenAI


class LLMProvider(ABC):
    """Minimal interface — every provider just needs `generate`."""

    @abstractmethod
    def generate(self, messages: list[dict]) -> str:
        ...


class OpenAIProvider(LLMProvider):
    """Calls the OpenAI chat-completions API."""

    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    def generate(self, messages: list[dict]) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=0.7,
        )
        return response.choices[0].message.content


class OllamaProvider(LLMProvider):
    """Stub — implement when Ollama integration is needed."""

    def __init__(self):
        # Ollama HTTP API (default port is 11434)
        self.url = os.getenv("OLLAMA_URL", "http://localhost:11434")
        self.model = os.getenv("OLLAMA_MODEL", "llama2")

    def _messages_to_prompt(self, messages: list[dict]) -> str:
        # Simple conversion: label roles and join into one prompt string.
        parts = []
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            parts.append(f"{role.upper()}: {content}")
        return "\n\n".join(parts)

    def generate(self, messages: list[dict]) -> str:
        prompt = self._messages_to_prompt(messages)
        endpoint = f"{self.url}/api/generate"
        payload = {"model": self.model, "prompt": prompt}
        try:
            resp = requests.post(endpoint, json=payload, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise RuntimeError(f"Ollama request failed: {e}")
        # Ollama may stream NDJSON or return JSON depending on server settings.
        text = resp.text or ""

        # If response looks like NDJSON (many JSON objects separated by newlines), parse each line
        parts: list[str] = []
        if "\n{" in text or resp.headers.get("content-type", "").lower().find("ndjson") != -1:
            for line in text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except ValueError:
                    # Skip non-JSON fragments
                    continue
                # Common Ollama streaming field is 'response'
                if isinstance(obj, dict):
                    if "response" in obj:
                        parts.append(str(obj.get("response", "")))
                    elif "output" in obj:
                        out = obj.get("output")
                        if isinstance(out, list):
                            parts.extend(str(x) for x in out)
                        else:
                            parts.append(str(out))
                    elif "content" in obj:
                        parts.append(str(obj.get("content", "")))
            if parts:
                return "".join(parts)

        # Otherwise, try to parse as regular JSON
        try:
            data = resp.json()
        except ValueError:
            # Fallback: return raw text
            return text

        # The structure depends on Ollama version. Try common fields.
        if isinstance(data, dict):
            if "output" in data:
                out = data["output"]
                if isinstance(out, list):
                    return "".join(str(x) for x in out)
                return str(out)
            if "response" in data:
                return str(data["response"])
            if "content" in data:
                return str(data["content"])

        # Fallback: return pretty-printed JSON as string
        return json.dumps(data)


def get_llm_provider() -> LLMProvider:
    """Factory: reads LLM_PROVIDER env var (default: openai)."""
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    if provider == "openai":
        return OpenAIProvider()
    if provider == "ollama":
        return OllamaProvider()
    raise ValueError(f"Unknown LLM_PROVIDER: {provider}")
