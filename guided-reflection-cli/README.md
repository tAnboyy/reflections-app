# Guided Reflection CLI

Separate terminal-first prototype for guided student reflection sessions.

This subproject is intentionally isolated from the existing `backend/` and `frontend/` application. It uses educator-authored YAML templates, a LangGraph-style turn controller, local file storage, and a future-ready memory provider interface.

## Features

- Template-driven reflection sessions
- Goal-directed agenda atom tracking
- Required-question completion gates
- Configurable question caps and early-stop handling
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
guided-reflection run --template .\examples\templates\critical_reflection_example.yaml --student .\examples\students\student_example.yaml --max-questions 5
```

## Template Format

Templates are YAML files with:

- topic and assignment metadata
- agenda atoms with acceptance rules
- optional legacy question bank entries
- rubric criteria
- session policies

See [examples/templates/critical_reflection_example.yaml](/d:/Projects_1/reflections-app/guided-reflection-cli/examples/templates/critical_reflection_example.yaml).

## Where Educators Maintain The Agenda

- In agenda-first templates, maintain the reflection agenda in `agenda_atoms`.
- Each `agenda_atoms[*].description` is the primary educator-authored focus for a turn.
- Each `agenda_atoms[*].acceptance_rules` defines what counts as enough evidence for that agenda item.
- `question_bank` is now a legacy authoring path for older templates that still want exact student-facing prompts.
- `policies` controls style and capture behavior, including `authoring_mode`, `conversation_style`, `max_questions`, and `max_turns`.

## How Sessions Stop

- The session completes when required agenda coverage is satisfied and any synthesis step is done.
- `policies.max_questions` caps the number of assistant questions directly.
- `policies.max_turns` remains a backstop on the number of student reply turns.
- The CLI also finalizes early on `exit`, `quit`, keyboard interrupt, or short replies such as "can we stop" / "no more questions".

See [examples/templates/new_template.yaml](/d:/Projects_1/reflections-app/guided-reflection-cli/examples/templates/new_template.yaml) for the new agenda-first format.

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
