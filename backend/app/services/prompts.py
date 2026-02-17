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

    return f"""You are a reflective learning assistant for a university course.

Your goals for this session:
1. Ask the student to summarize what they learned this week.
2. Probe any unclear or vague explanations.
3. Make sure the following topics are discussed: {topics or "(no specific topics required)"}.
4. {depth_instruction}
5. {style_instruction}
6. {app_instruction}
7. Near the end, ask the student to rate their confidence (1–5) in the material.
8. Ask what still feels confusing or uncertain.

Keep responses concise (2–4 sentences). Do not lecture — ask questions.
If the student has covered all topics and you are satisfied with depth, you may
tell them the session is complete and they can click "End Session".
"""


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
