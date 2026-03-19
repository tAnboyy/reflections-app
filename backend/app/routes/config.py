"""Routes — ModuleConfig CRUD + subtopic generation."""

import json
import re

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ModuleConfig, Module
from app.schemas import ModuleConfigCreate, ModuleConfigOut, SubtopicGenerateRequest, SubtopicGenerateResponse
from app.services.llm import get_llm_provider
from app.services.prompts import build_subtopic_generation_prompt

router = APIRouter(prefix="/api/modules", tags=["config"])


@router.get("/{module_id}/config", response_model=ModuleConfigOut)
def get_config(module_id: str, db: Session = Depends(get_db)):
    cfg = db.query(ModuleConfig).filter(ModuleConfig.module_id == module_id).first()
    if not cfg:
        raise HTTPException(404, "Config not found for this module")
    return cfg


@router.post("/{module_id}/config", response_model=ModuleConfigOut, status_code=201)
def create_config(module_id: str, body: ModuleConfigCreate, db: Session = Depends(get_db)):
    # Ensure module exists
    module = db.query(Module).filter(Module.id == module_id).first()
    if not module:
        raise HTTPException(404, "Module not found")
    # Upsert — replace existing config if present
    existing = db.query(ModuleConfig).filter(ModuleConfig.module_id == module_id).first()
    if existing:
        for key, val in body.model_dump().items():
            setattr(existing, key, val)
        db.commit()
        db.refresh(existing)
        return existing
    cfg = ModuleConfig(module_id=module_id, **body.model_dump())
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


@router.put("/{module_id}/config", response_model=ModuleConfigOut)
def update_config(module_id: str, body: ModuleConfigCreate, db: Session = Depends(get_db)):
    cfg = db.query(ModuleConfig).filter(ModuleConfig.module_id == module_id).first()
    if not cfg:
        raise HTTPException(404, "Config not found")
    for key, val in body.model_dump().items():
        setattr(cfg, key, val)
    db.commit()
    db.refresh(cfg)
    return cfg


@router.post("/subtopics/generate", response_model=SubtopicGenerateResponse)
def generate_subtopics(body: SubtopicGenerateRequest):
    """Auto-generate sub-topics from main topics using LLM."""
    if not body.main_topics:
        raise HTTPException(400, "main_topics must not be empty")
    llm = get_llm_provider()
    prompt = build_subtopic_generation_prompt(body.main_topics)
    try:
        raw = llm.generate([{"role": "user", "content": prompt}])
        text = re.sub(r"^```[a-z]*\n?", "", raw.strip(), flags=re.MULTILINE).strip("`").strip()
        sub_topics = json.loads(text)
        if not isinstance(sub_topics, list):
            raise ValueError("Not a list")
        sub_topics = [str(t).strip() for t in sub_topics if str(t).strip()]
    except Exception as e:
        raise HTTPException(500, f"Failed to generate sub-topics: {str(e)}")
    return SubtopicGenerateResponse(sub_topics=sub_topics)
