from datetime import datetime
import uuid

from sqlalchemy import (
    ARRAY,
    JSON,
    Boolean,
    Column,
    DateTime,
    Float,
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


class DocumentLinkORM(Base):
    __tablename__ = "document_links"
    __table_args__ = (
        Index("ix_document_links_source", "source_document_id"),
        Index("ix_document_links_target", "target_document_id"),
        Index("ix_document_links_kind", "kind"),
        Index("ix_document_links_relation", "relation"),
        Index("uq_document_links_tuple", "source_document_id", "target_document_id", "kind", "relation", unique=True),
        {"comment": "Graph edges between documents (explicit + semantic)"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    target_document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    kind = Column(String(20), nullable=False, default="explicit")  # explicit|semantic|derived
    relation = Column(String(50), nullable=False, default="references")  # references|similar_to|contains
    weight = Column(Float, nullable=False, default=1.0)
    evidence = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class UserORM(Base):
    __tablename__ = "users"

    id = Column(String(255), primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    display_name = Column(String(255))
    password_hash = Column(String(255))
    is_active = Column(Boolean, nullable=False, default=True)
    is_admin = Column(Boolean, nullable=False, default=False)
    role = Column(String(50), nullable=False, default="member")


class GroupORM(Base):
    __tablename__ = "groups"

    id = Column(String(255), primary_key=True)
    name = Column(String(255), nullable=False)


class UserGroupORM(Base):
    __tablename__ = "user_groups"

    user_id = Column(String(255), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group_id = Column(String(255), ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)


class UserGroupOverrideORM(Base):
    __tablename__ = "user_group_overrides"

    user_id = Column(String(255), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    group_id = Column(String(255), ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)
    effect = Column(String(10), nullable=False, default="deny")
    reason = Column(Text)
    created_by = Column(String(255))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class UserDocumentOverrideORM(Base):
    __tablename__ = "user_document_overrides"

    user_id = Column(String(255), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    effect = Column(String(10), nullable=False, default="deny")
    reason = Column(Text)
    created_by = Column(String(255))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class DocumentPermissionORM(Base):
    __tablename__ = "document_permissions"

    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    group_id = Column(String(255), ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True)


class EntityORM(Base):
    __tablename__ = "entities"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False, index=True)
    normalized_name = Column(String(255), index=True)
    entity_type = Column(String(100))


class EntityRelationORM(Base):
    __tablename__ = "entity_relations"
    __table_args__ = (
        Index("uq_entity_relations_triplet", "source_id", "target_id", "relation_type", unique=True),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"))
    target_id = Column(UUID(as_uuid=True), ForeignKey("entities.id"))
    relation_type = Column(String(100))


class DocumentEntityORM(Base):
    __tablename__ = "document_entities"

    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    entity_type = Column(String(100), nullable=False)


class EntityAliasORM(Base):
    __tablename__ = "entity_aliases"

    entity_id = Column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True)
    normalized_alias = Column(String(255), primary_key=True)
    alias_value = Column(String(255), nullable=False)
    alias_type = Column(String(100), nullable=False, default="identity")
    alias_strength = Column(Integer, nullable=False, default=1)


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


class SRSDraftORM(Base):
    __tablename__ = "srs_drafts"
    __table_args__ = {"comment": "AI-generated SRS drafts created from selected sources"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    source_document_ids = Column(JSON, default=list)  # list[str] of document UUIDs
    source_snapshot = Column(JSON, default=dict)  # stores source titles/urls/snippets at creation time
    question = Column(Text)
    answer = Column(Text)
    created_by = Column(String(255), index=True)
    status = Column(String(30), nullable=False, default="draft")  # draft|published|archived
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


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
    scope_group_id = Column(String(255))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    confirmed_at = Column(DateTime)
    submitted_at = Column(DateTime)


class SyncLogORM(Base):
    __tablename__ = "sync_logs"
    __table_args__ = {"comment": "Track incremental sync state per connector"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    connector = Column(String(255), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="running")
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    last_sync_at = Column(DateTime, index=True)
    fetched = Column(Integer, default=0)
    indexed = Column(Integer, default=0)
    errors = Column(Integer, default=0)


class ConnectorInstanceORM(Base):
    __tablename__ = "connector_instances"
    __table_args__ = {"comment": "Multi-instance connector registry (credentials + base url)"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connector_type = Column(String(50), nullable=False, index=True)  # confluence|jira|slack|file_server
    name = Column(String(255), nullable=False)
    base_url = Column(Text)
    auth_type = Column(String(50), nullable=False, default="token")  # token|basic
    username = Column(String(255))
    secret = Column(Text)  # api token / password / bot token (on-prem demo storage)
    extra = Column(JSON, default={})
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


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
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) NOT NULL DEFAULT 'member'"
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
            "ALTER TABLE entities ADD COLUMN IF NOT EXISTS normalized_name VARCHAR(255)"
        ))
        await conn.execute(text(
            "UPDATE entities SET normalized_name = LOWER(name) WHERE normalized_name IS NULL"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_entities_normalized_name ON entities (normalized_name)"
        ))
        await conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_entity_relations_triplet "
            "ON entity_relations (source_id, target_id, relation_type)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_chunks_fts "
            "ON chunks USING GIN (to_tsvector('simple', content))"
        ))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS document_entities (
                document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                entity_type VARCHAR(100) NOT NULL,
                PRIMARY KEY (document_id, entity_id)
            )
        """))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS entity_aliases (
                entity_id UUID NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
                normalized_alias VARCHAR(255) NOT NULL,
                alias_value VARCHAR(255) NOT NULL,
                alias_type VARCHAR(100) NOT NULL DEFAULT 'identity',
                alias_strength INTEGER NOT NULL DEFAULT 1,
                PRIMARY KEY (entity_id, normalized_alias)
            )
        """))
        await conn.execute(text(
            "ALTER TABLE entity_aliases ADD COLUMN IF NOT EXISTS alias_strength INTEGER NOT NULL DEFAULT 1"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_entity_aliases_normalized_alias "
            "ON entity_aliases (normalized_alias)"
        ))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ai_task_drafts (
                id UUID PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                source_type VARCHAR(50) NOT NULL,
                source_ref TEXT,
                source_summary TEXT,
                source_url TEXT,
                source_meta JSON NOT NULL DEFAULT '{}'::json,
                evidence JSON NOT NULL DEFAULT '[]'::json,
                suggested_fields JSON NOT NULL DEFAULT '{}'::json,
                dedup_key TEXT,
                issue_type VARCHAR(30) NOT NULL DEFAULT 'Task',
                epic_key VARCHAR(50),
                suggested_assignee VARCHAR(255),
                priority VARCHAR(20) NOT NULL DEFAULT 'Medium',
                labels TEXT[] DEFAULT ARRAY[]::TEXT[],
                components TEXT[] DEFAULT ARRAY[]::TEXT[],
                due_date DATE,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                triggered_by VARCHAR(50) NOT NULL DEFAULT 'scheduler',
                created_by VARCHAR(255),
                confirmed_by VARCHAR(255),
                jira_key VARCHAR(50),
                jira_project VARCHAR(50) NOT NULL DEFAULT 'ECOS2025',
                scope_group_id VARCHAR(255),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                confirmed_at TIMESTAMP,
                submitted_at TIMESTAMP
            )
        """))
        await conn.execute(text(
            "ALTER TABLE ai_task_drafts ADD COLUMN IF NOT EXISTS source_url TEXT"
        ))
        await conn.execute(text(
            "ALTER TABLE ai_task_drafts ADD COLUMN IF NOT EXISTS source_meta JSON NOT NULL DEFAULT '{}'::json"
        ))
        await conn.execute(text(
            "ALTER TABLE ai_task_drafts ADD COLUMN IF NOT EXISTS dedup_key TEXT"
        ))
        await conn.execute(text(
            "ALTER TABLE ai_task_drafts ADD COLUMN IF NOT EXISTS evidence JSON NOT NULL DEFAULT '[]'::json"
        ))
        await conn.execute(text(
            "ALTER TABLE ai_task_drafts ADD COLUMN IF NOT EXISTS suggested_fields JSON NOT NULL DEFAULT '{}'::json"
        ))
        await conn.execute(text(
            "ALTER TABLE ai_task_drafts ADD COLUMN IF NOT EXISTS components TEXT[] DEFAULT ARRAY[]::TEXT[]"
        ))
        await conn.execute(text(
            "ALTER TABLE ai_task_drafts ADD COLUMN IF NOT EXISTS due_date DATE"
        ))
        await conn.execute(text(
            "ALTER TABLE ai_task_drafts ADD COLUMN IF NOT EXISTS issue_type VARCHAR(30) NOT NULL DEFAULT 'Task'"
        ))
        await conn.execute(text(
            "ALTER TABLE ai_task_drafts ADD COLUMN IF NOT EXISTS epic_key VARCHAR(50)"
        ))
        await conn.execute(text(
            "ALTER TABLE ai_task_drafts ADD COLUMN IF NOT EXISTS scope_group_id VARCHAR(255)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_ai_task_drafts_dedup_key ON ai_task_drafts (dedup_key)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_ai_task_drafts_scope_group_id ON ai_task_drafts (scope_group_id)"
        ))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS connector_configs (
                connector VARCHAR(255) PRIMARY KEY,
                enabled BOOLEAN NOT NULL DEFAULT TRUE,
                auto_sync BOOLEAN NOT NULL DEFAULT FALSE,
                schedule_hour INTEGER,
                schedule_minute INTEGER,
                schedule_tz VARCHAR(64) NOT NULL DEFAULT 'Asia/Ho_Chi_Minh',
                selection JSON NOT NULL DEFAULT '{}'::json,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text(
            "ALTER TABLE connector_configs ALTER COLUMN connector TYPE VARCHAR(255)"
        ))
        await conn.execute(text(
            "ALTER TABLE sync_logs ALTER COLUMN connector TYPE VARCHAR(255)"
        ))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS connector_instances (
                id UUID PRIMARY KEY,
                connector_type VARCHAR(50) NOT NULL,
                name VARCHAR(255) NOT NULL,
                base_url TEXT,
                auth_type VARCHAR(50) NOT NULL DEFAULT 'token',
                username VARCHAR(255),
                secret TEXT,
                extra JSON NOT NULL DEFAULT '{}'::json,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_connector_instances_type ON connector_instances (connector_type)"
        ))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_group_overrides (
                user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                group_id VARCHAR(255) NOT NULL REFERENCES groups(id) ON DELETE CASCADE,
                effect VARCHAR(10) NOT NULL DEFAULT 'deny',
                reason TEXT,
                created_by VARCHAR(255),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                PRIMARY KEY (user_id, group_id)
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_user_group_overrides_group_id ON user_group_overrides (group_id)"
        ))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_document_overrides (
                user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                effect VARCHAR(10) NOT NULL DEFAULT 'deny',
                reason TEXT,
                created_by VARCHAR(255),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                PRIMARY KEY (user_id, document_id)
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_user_document_overrides_document_id ON user_document_overrides (document_id)"
        ))
