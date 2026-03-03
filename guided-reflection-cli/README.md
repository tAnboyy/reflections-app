# Guided Reflection CLI (lean agent)

LangGraph-based tutor that keeps a per-student memory store and uses a single prompts file. OpenAI Chat models only.

## Install

```bash
cd guided-reflection-cli
python -m venv .venv
.venv\Scripts\activate
pip install -e .
```

## Run

```bash
# With a YAML agenda file
guided-reflection run ^
  --agenda .\examples\templates\new_template.yaml ^
  --student-id student-001 ^
  --profile .\examples\students\student_example.yaml ^
  --submissions .\examples\students\latest.md

# Or with a plain-text agenda paragraph
guided-reflection run ^
  --agenda-text "Reflect on your project idea and what success would look like." ^
  --student-id student-001
```

Options:
- `--max-turns INT` (default 12 or agenda value)
- `--model` (defaults to `OPENAI_MODEL` or `gpt-4o-mini`)
- `--output-dir` (defaults to `data/runs`)

Required env: `OPENAI_API_KEY` (and optional `OPENAI_MODEL`).

## Data layout
- `data/students/{id}/profile.yaml` (source of truth)
- `data/students/{id}/notes.md` (running bullets)
- `data/students/{id}/history.json` (recent runs with summaries)
- `data/runs/{timestamp}_{template}_{student}/report.md`, `transcript.md`, `state.json`

## Prompts
All system, planner, question, evaluator, and summary prompts live in `src/guided_reflection_cli/agent/prompts.yaml`.

## Behavior highlights
- Conversation director plans next move (ask, pivot, scaffold, synthesize, stop).
- Gentle, non-grading tone; one open question per turn; optional scaffold when stuck.
- Honors stop intent immediately (e.g., “please end”, “no idea please end this”).
- Appends session bullets to student notes and history after each run.
