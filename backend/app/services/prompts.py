"""Prompt templates — professor-config-aware prompts for reflection and evaluation."""


def build_reflection_prompt(config: dict) -> str:
    """Build the chatbot system prompt from a ModuleConfig dict.

    The prompt instructs the LLM to act as a reflective learning assistant
    whose behaviour adapts to the professor's settings.
    """
    topics = ", ".join(config.get("required_topics", []))
    depth = config.get("expected_depth", "surface")
    style = config.get("probing_style", "supportive")
    require_app = config.get("must_include_application", False)
    custom_notes = config.get("custom_notes", "").strip()

    style_instruction = {
        "supportive": "Be warm, encouraging, and patient. Gently guide the student.",
        "socratic": "Use the Socratic method — ask probing counter-questions to deepen thinking.",
    }.get(style, "Be warm and encouraging.")

    depth_instruction = {
        "surface": "Accept brief summaries but encourage a bit more detail.",
        "applied": "Push the student to connect concepts to real-world applications.",
        "analytical": "Expect the student to compare, contrast, and critically evaluate ideas.",
    }.get(depth, "Accept brief summaries.")

    app_instruction = (
        "You MUST ask at least one question requiring the student to apply a concept to a real scenario."
        if require_app
        else ""
    )

    custom_notes_block = (
        f"\nPROFESSOR NOTES (highest priority — address these first):\n{custom_notes}\n"
        if custom_notes
        else ""
    )

    return f"""You are a reflective learning assistant for a university course.
{custom_notes_block}
TOPIC LIST:
{topics or "(no specific topics required)"}

SESSION RULES — follow these exactly:
1. OPENING MESSAGE: Ask only the first question. No greeting prefix, no "Correct", just the question.
2. The session lasts 10 minutes. Do NOT rush. Spend 2-3 exchanges per topic before moving on — ask follow-up questions to probe understanding, request examples, or push for deeper explanation.
3. After each student reply, judge their answer:
   - Correct or adequate: one brief acknowledgment sentence, then ask a follow-up or the next topic question.
   - Wrong or misconception: correct in 2-3 plain sentences explaining the right idea, then ask the next question.
4. {depth_instruction}
5. {style_instruction}
6. {app_instruction}
7. Only after all topics are covered thoroughly, ask the student to rate their confidence (1-5).
8. Then ask what still feels confusing, then tell them they can click "End Session".
9. If the student message starts with a time tag like "[1:30 remaining]", wrap up: finish the current topic, ask confidence, ask what's confusing, then close.

FORMAT RULES:
- Plain text only. No markdown, no asterisks, no bold.
- One question per turn. Never ask two questions at once."""


def build_evaluation_prompt(transcript: str, config: dict) -> str:
    """Build the evaluation prompt sent after a session ends.

    The LLM should return a strict JSON object scored relative to the
    professor's expectations.
    """
    topics = ", ".join(config.get("required_topics", []))
    depth = config.get("expected_depth", "surface")

    return f"""You are an educational evaluation engine.

Below is a transcript of a student reflection session and the professor's expectations.

PROFESSOR EXPECTATIONS:
- Required topics: {topics or "none specified"}
- Expected depth: {depth}

TRANSCRIPT:
{transcript}

Evaluate this transcript and return ONLY a JSON object (no explanation, no markdown):

{{
  "topics_covered": ["list of topics the student discussed"],
  "missing_topics": ["required topics NOT discussed"],
  "misconceptions": ["any factual errors or misunderstandings detected"],
  "reflection_depth_score": <float 0-1, where 1 = fully meets {depth} depth>,
  "confidence_level": <int 1-5, from student self-report or inferred>,
  "engagement_score": <float 0-1, based on detail and effort shown>
}}

Return ONLY valid JSON. No extra text.
"""
