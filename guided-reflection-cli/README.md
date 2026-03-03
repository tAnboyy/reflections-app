# Guided Reflection CLI

Separate terminal-first prototype for guided student reflection sessions.

This subproject is intentionally isolated from the existing `backend/` and `frontend/` application. It uses educator-authored YAML templates, a LangGraph-style turn controller, local file storage, and a future-ready memory provider interface.

## Features

- Template-driven reflection sessions
- Goal-directed agenda atom tracking
- Required-question completion gates
- Interactive CLI flow for students
- JSON and Markdown output artifacts per run
- Offline-friendly fake provider for tests and local development

## Install

```bash
cd guided-reflection-cli
python -m venv .venv
.venv\Scripts\activate
pip install -e .[dev]
```

## Environment

Copy `.env.example` to `.env` if you want live model-backed question phrasing and final summaries.

Key variables:

- `LLM_PROVIDER`: `openai`, `ollama`, or `fake`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OLLAMA_BASE_URL`
- `OLLAMA_MODEL`

Default runtime values:

- `LLM_PROVIDER=openai`
- `OPENAI_MODEL=gpt-4o-mini`

For offline development and tests:

```bash
$env:LLM_PROVIDER="fake"
```

## Commands

```bash
guided-reflection template init .\examples\templates\new_template.yaml
guided-reflection template validate .\examples\templates\critical_reflection_example.yaml
guided-reflection run --template .\examples\templates\critical_reflection_example.yaml --student .\examples\students\student_example.yaml
```

## Template Format

Templates are YAML files with:

- topic and assignment metadata
- agenda atoms with acceptance rules
- required and optional question bank entries
- rubric criteria
- session policies

See [examples/templates/critical_reflection_example.yaml](/d:/Projects_1/reflections-app/guided-reflection-cli/examples/templates/critical_reflection_example.yaml).

## Student Profile Format

Student profiles are YAML files with:

- `student_id`
- basic personalization preferences
- strengths
- growth areas
- notes

See [examples/students/student_example.yaml](/d:/Projects_1/reflections-app/guided-reflection-cli/examples/students/student_example.yaml).

## Output Artifacts

Each run writes a folder under `runs/` containing:

- `result.json`
- `report.md`
- `transcript.md`

## Limitations

- Retrieval and PageIndex integration are deferred by design in this MVP.
- The acceptance gate is deterministic and file-local.
- `ollama` is reserved as a future provider mode and is not fully implemented yet.
