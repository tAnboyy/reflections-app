"""Routes — Reflection Chat (start / message / end)."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ModuleConfig, Conversation, Student, ReflectionAnalytics
from app.schemas import (
    ChatStartRequest, ChatStartResponse,
    ChatMessageRequest, ChatMessageResponse,
    ChatEndRequest, ChatEndResponse,
)
from app.services import chat_service
from app.services.llm import get_llm_provider
from app.services.evaluation import evaluate_transcript

router = APIRouter(prefix="/api/chat", tags=["chat"])


def _generate_anonymized_id() -> str:
    """Generate a compact, collision-resistant anonymized student ID."""
    return f"anon-{uuid4().hex[:12]}"


@router.post("/start", response_model=ChatStartResponse)
def start_chat(body: ChatStartRequest, db: Session = Depends(get_db)):
    try:
        # Ensure student exists (auto-create for prototype convenience)
        student = db.query(Student).filter(Student.id == body.student_id).first()
        if not student:
            student = Student(id=body.student_id, anonymized_id=_generate_anonymized_id())
            db.add(student)
            try:
                db.commit()
            except IntegrityError:
                # Roll back and re-check in case another request inserted the same student.
                db.rollback()
                student = db.query(Student).filter(Student.id == body.student_id).first()
                if not student:
                    # Extremely unlikely: anonymized_id collision for a different student.
                    student = Student(id=body.student_id, anonymized_id=_generate_anonymized_id())
                    db.add(student)
                    db.commit()

        # Load module config
        cfg = db.query(ModuleConfig).filter(ModuleConfig.module_id == body.module_id).first()
        if not cfg:
            raise HTTPException(404, "ModuleConfig not found — professor must configure first")

        config_dict = {
            "required_topics": cfg.required_topics or [],
            "sub_topics": cfg.sub_topics or [],
            "expected_depth": cfg.expected_depth,
            "probing_style": cfg.probing_style,
            "must_include_application": cfg.must_include_application,
            "custom_notes": cfg.custom_notes or "",
        }

        # Cross-session memory: query past weak areas for this student+module
        past = (
            db.query(ReflectionAnalytics)
            .join(Conversation, ReflectionAnalytics.conversation_id == Conversation.id)
            .filter(
                Conversation.student_id == body.student_id,
                Conversation.module_id == body.module_id,
            )
            .order_by(desc(Conversation.created_at))
            .limit(3)
            .all()
        )
        past_weak = list({t for r in past for t in (r.missing_topics or [])})

        llm = get_llm_provider()
        session_id, greeting, total_questions = chat_service.start_session(
            student_id=body.student_id,
            module_id=body.module_id,
            config=config_dict,
            llm=llm,
            past_weak_areas=past_weak,
        )
        return ChatStartResponse(
            session_id=session_id,
            greeting=greeting,
            total_questions=total_questions,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Failed to start chat session: {str(e)}")


@router.post("/message", response_model=ChatMessageResponse)
def send_message(body: ChatMessageRequest):
    llm = get_llm_provider()
    try:
        reply, question_index, total_questions, is_bonus_phase = chat_service.send_message(
            body.session_id, body.message, llm, body.time_remaining
        )
    except KeyError:
        raise HTTPException(404, "Session not found")
    return ChatMessageResponse(
        reply=reply,
        question_index=question_index,
        total_questions=total_questions,
        is_bonus_phase=is_bonus_phase,
    )


@router.post("/end", response_model=ChatEndResponse)
def end_chat(body: ChatEndRequest, db: Session = Depends(get_db)):
    try:
        session = chat_service.end_session(body.session_id)
    except KeyError:
        raise HTTPException(404, "Session not found")

    transcript = chat_service.format_transcript(session.messages)

    # Persist conversation
    convo = Conversation(
        student_id=session.student_id,
        module_id=session.module_id,
        transcript=transcript,
    )
    db.add(convo)
    db.commit()
    db.refresh(convo)

    # Evaluate
    llm = get_llm_provider()
    eval_result = evaluate_transcript(
        conversation_id=convo.id,
        transcript=transcript,
        config=session.config,
        llm=llm,
        db=db,
    )

    return ChatEndResponse(conversation_id=convo.id, evaluation=eval_result)
