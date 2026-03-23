import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from storage.db.db import Base

class ChatSession(Base):
    __tablename__ = "chat_sessions"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, index=True, nullable=False)
    title = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True, nullable=False)
    role = Column(String(50), nullable=False)  # 'user' hoặc 'assistant'
    content = Column(Text, nullable=False)
    sources = Column(JSONB, default=list)
    agent_plan = Column(JSONB, default=list)   # Lưu trữ kế hoạch của agent
    rewritten_query = Column(Text, nullable=True) # Lưu trữ query đã được rewrite
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    session = relationship("ChatSession", back_populates="messages")


class ChatJob(Base):
    __tablename__ = "chat_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id = Column(String(36), ForeignKey("chat_sessions.id", ondelete="CASCADE"), index=True, nullable=True)
    user_id = Column(String, index=True, nullable=False)
    question = Column(Text, nullable=False)
    status = Column(String(20), default="queued", index=True)  # queued, running, completed, failed
    progress = Column(Integer, default=0)
    thoughts = Column(JSONB, default=list)  # List of ReAct steps / thoughts
    result = Column(JSONB, default=dict)    # {answer: "", sources: []}
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))