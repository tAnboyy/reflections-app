"""Pydantic schemas for request / response validation."""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel


# ── Module ───────────────────────────────────────────────────────────────────
class ModuleCreate(BaseModel):
    name: str

class ModuleOut(BaseModel):
    id: str
    name: str
    model_config = {"from_attributes": True}


# ── ModuleConfig ─────────────────────────────────────────────────────────────
class ModuleConfigCreate(BaseModel):
    required_topics: list[str] = []
    expected_depth: str = "surface"       # surface | applied | analytical
    probing_style: str = "supportive"     # supportive | socratic
    must_include_application: bool = False
    custom_notes: str = ""

class ModuleConfigOut(ModuleConfigCreate):
    id: str
    module_id: str
    model_config = {"from_attributes": True}


# ── Chat ─────────────────────────────────────────────────────────────────────
class ChatStartRequest(BaseModel):
    student_id: str
    module_id: str

class ChatStartResponse(BaseModel):
    session_id: str
    greeting: str

class ChatMessageRequest(BaseModel):
    session_id: str
    message: str
    time_remaining: int = 600  # seconds remaining in session

class ChatMessageResponse(BaseModel):
    reply: str

class ChatEndRequest(BaseModel):
    session_id: str

class ChatEndResponse(BaseModel):
    conversation_id: str
    evaluation: EvaluationOut | None = None


# ── Evaluation ───────────────────────────────────────────────────────────────
class EvaluationOut(BaseModel):
    topics_covered: list[str] = []
    missing_topics: list[str] = []
    misconceptions: list[str] = []
    reflection_depth_score: float = 0.0
    confidence_level: int = 0
    engagement_score: float = 0.0
    model_config = {"from_attributes": True}


# ── Analytics row (dashboard) ────────────────────────────────────────────────
class AnalyticsRow(BaseModel):
    conversation_id: str
    student_anonymized_id: str
    reflection_depth_score: float
    confidence_level: int
    engagement_score: float
    misconceptions: list[str]
    missing_topics: list[str]
    created_at: str
    model_config = {"from_attributes": True}


# ── Student ──────────────────────────────────────────────────────────────────
class StudentCreate(BaseModel):
    anonymized_id: str

class StudentOut(BaseModel):
    id: str
    anonymized_id: str
    model_config = {"from_attributes": True}


# Forward-ref update so ChatEndResponse can reference EvaluationOut
ChatEndResponse.model_rebuild()
