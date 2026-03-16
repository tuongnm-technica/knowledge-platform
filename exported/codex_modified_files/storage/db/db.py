from datetime import datetime
import uuid

from sqlalchemy import (
    ARRAY,
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config.settings import settings


engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG, pool_size=10)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class DocumentORM(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("uq_documents_source_source_id", "source", "source_id", unique=True),
        {"comment": "Core knowledge units ingested from external systems"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source = Column(String(50), nullable=False, index=True)
    source_id = Column(String(255), nullable=False)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    url = Column(Text)
    author = Column(String(255))
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False, index=True)
    metadata_ = Column("metadata", JSON, default={})
    permissions = Column(ARRAY(String), default=[])
    entities = Column(ARRAY(String), default=[])
    workspace_id = Column(String(255), index=True)


class ChunkORM(Base):
    __tablename__ = "chunks"
    __table_args__ = {"comment": "Sub-segments of documents; embeddings stored in Qdrant"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)


class UserORM(Base):
    __tablename__ = "users"

    id = Column(String(255), primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    display_name = Column(String(255))
    password_hash = Column(String(255))
    is_active = Column(Boolean, nullable=False, default=True)
    is_admin = Column(Boolean, nullable=False, default=False)


class GroupORM(Base):
    __tablename__ = "groups"

    id = Column(String(255), primary_key=True)
    name = Column(String(255), nullable=False)


class UserGroupORM(Base):
    __tablename__ = "user_groups"

    user_id = Column(String(255), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group_id = Column(String(255), ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)


class DocumentPermissionORM(Base):
    __tablename__ = "document_permissions"

    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    group_id = Column(String(255), ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)


class EntityORM(Base):
    __tablename__ = "entities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    entity_type = Column(String(100))


class EntityRelationORM(Base):
    __tablename__ = "entity_relations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"))
    target_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"))
    relation_type = Column(String(100))


class QueryLogORM(Base):
    __tablename__ = "query_logs"
    __table_args__ = {"comment": "Analytics: track queries for ranking improvement"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), index=True)
    query = Column(Text, nullable=False)
    rewritten_query = Column(Text)
    result_count = Column(Integer, default=0)
    created_at = Column(DateTime)


class DocumentSummaryORM(Base):
    __tablename__ = "document_summaries"

    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    summary = Column(Text, nullable=False)


class AITaskDraftORM(Base):
    __tablename__ = "ai_task_drafts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text, nullable=False)
    description = Column(Text)
    source_type = Column(String(50), nullable=False)
    source_ref = Column(Text)
    source_summary = Column(Text)
    suggested_assignee = Column(String(255))
    priority = Column(String(20), nullable=False, default="Medium")
    labels = Column(ARRAY(String), default=[])
    status = Column(String(20), nullable=False, default="pending")
    triggered_by = Column(String(50), nullable=False, default="scheduler")
    created_by = Column(String(255))
    confirmed_by = Column(String(255))
    jira_key = Column(String(50))
    jira_project = Column(String(50), nullable=False, default="ECOS2025")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    confirmed_at = Column(DateTime)
    submitted_at = Column(DateTime)


class SyncLogORM(Base):
    __tablename__ = "sync_logs"
    __table_args__ = {"comment": "Track incremental sync state per connector"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    connector = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="running")
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    last_sync_at = Column(DateTime, index=True)
    fetched = Column(Integer, default=0)
    indexed = Column(Integer, default=0)
    errors = Column(Integer, default=0)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS workspace_id VARCHAR(255)"
        ))
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255)"
        ))
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE"
        ))
        await conn.execute(text(
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT FALSE"
        ))
        await conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_documents_source_source_id "
            "ON documents (source, source_id)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_documents_workspace_id "
            "ON documents (workspace_id)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_chunks_fts "
            "ON chunks USING GIN (to_tsvector('simple', content))"
        ))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ai_task_drafts (
                id UUID PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                source_type VARCHAR(50) NOT NULL,
                source_ref TEXT,
                source_summary TEXT,
                suggested_assignee VARCHAR(255),
                priority VARCHAR(20) NOT NULL DEFAULT 'Medium',
                labels TEXT[] DEFAULT ARRAY[]::TEXT[],
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                triggered_by VARCHAR(50) NOT NULL DEFAULT 'scheduler',
                created_by VARCHAR(255),
                confirmed_by VARCHAR(255),
                jira_key VARCHAR(50),
                jira_project VARCHAR(50) NOT NULL DEFAULT 'ECOS2025',
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                confirmed_at TIMESTAMP,
                submitted_at TIMESTAMP
            )
        """))
