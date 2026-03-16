"""
tasks/models.py
ORM + Pydantic models cho ai_task_drafts.
Thêm vào storage/db/db.py hoặc import riêng.
"""
from sqlalchemy import Column, String, Text, DateTime, ARRAY, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid


# ─── ORM (thêm vào storage/db/db.py) ────────────────────────────────────────

class AITaskDraftORM:
    """Paste class này vào storage/db/db.py, kế thừa Base đã có sẵn."""
    __tablename__ = "ai_task_drafts"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title              = Column(Text, nullable=False)
    description        = Column(Text)
    source_type        = Column(String(50), nullable=False)   # slack | confluence
    source_ref         = Column(Text)
    source_summary     = Column(Text)
    suggested_assignee = Column(String(255))
    priority           = Column(String(20), default="Medium")
    labels             = Column(ARRAY(String), default=[])
    status             = Column(String(20), nullable=False, default="pending")
    triggered_by       = Column(String(50), default="scheduler")
    created_by         = Column(String(255))
    confirmed_by       = Column(String(255))
    jira_key           = Column(String(50))
    jira_project       = Column(String(50))
    created_at         = Column(DateTime, nullable=False, server_default=func.now())
    confirmed_at       = Column(DateTime)
    submitted_at       = Column(DateTime)


# ─── Pydantic schemas ────────────────────────────────────────────────────────

class TaskDraftOut(BaseModel):
    id:                 str
    title:              str
    description:        Optional[str] = None
    source_type:        str
    source_ref:         Optional[str] = None
    source_summary:     Optional[str] = None
    suggested_assignee: Optional[str] = None
    priority:           str = "Medium"
    labels:             list[str] = []
    status:             str
    triggered_by:       str
    jira_key:           Optional[str] = None
    jira_project:       Optional[str] = None
    created_at:         datetime

    class Config:
        from_attributes = True


class TaskDraftConfirm(BaseModel):
    """Body khi user confirm 1 task."""
    title:              Optional[str] = None        # user có thể edit
    description:        Optional[str] = None
    suggested_assignee: Optional[str] = None
    priority:           Optional[str] = None
    jira_project:       Optional[str] = None


class ExtractedTask(BaseModel):
    """Schema output của LLM khi extract tasks từ content."""
    title:              str
    description:        str
    suggested_assignee: Optional[str] = None
    priority:           str = "Medium"              # High | Medium | Low
    labels:             list[str] = []
    # Optional evidence fields (best-effort). For Slack, evidence_ts should be the message ts (e.g. 1710561234.567890).
    evidence_ts:        Optional[str] = None
    evidence:           Optional[str] = None
