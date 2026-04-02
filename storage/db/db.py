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
    create_engine,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config.settings import settings


engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG, pool_size=10)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

# Synchronous engine for maintenance/scripts if needed
sync_engine = create_engine(settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://"))
SyncSessionLocal = sessionmaker(bind=sync_engine)


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
    metadata_ = Column("metadata", JSONB, default={})
    permissions = Column(ARRAY(String), default=[])
    entities = Column(ARRAY(String), default=[])
    workspace_id = Column(String(255), index=True)
    summary = Column(Text)


class ChunkORM(Base):
    __tablename__ = "chunks"
    __table_args__ = {"comment": "Sub-segments of documents; embeddings stored in Qdrant"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    content = Column(Text, nullable=False)
    chunk_index = Column(Integer, nullable=False)


class DocumentAssetORM(Base):
    __tablename__ = "document_assets"
    __table_args__ = (
        Index("ix_document_assets_document_id", "document_id"),
        Index("ix_document_assets_sha256", "sha256"),
        {"comment": "Binary assets (images) attached to documents; stored on local disk"},
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    source = Column(String(50), nullable=False, index=True)
    source_ref = Column(Text)  # page_id / issue_key / slack file id / smb path ...
    kind = Column(String(20), nullable=False, default="image")  # image (future: pdf_page, audio, ...)
    filename = Column(Text)
    mime_type = Column(String(100))
    bytes = Column(Integer)
    sha256 = Column(String(64))
    local_path = Column(Text, nullable=False)  # relative to settings.ASSETS_DIR
    caption = Column(Text)
    ocr_text = Column(Text)
    width = Column(Integer)
    height = Column(Integer)
    meta = Column(JSON, default={})
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ChunkAssetORM(Base):
    __tablename__ = "chunk_assets"
    __table_args__ = (
        Index("ix_chunk_assets_chunk_id", "chunk_id"),
        Index("ix_chunk_assets_asset_id", "asset_id"),
        {"comment": "Join table: which assets are referenced by which chunks"},
    )

    chunk_id = Column(UUID(as_uuid=True), ForeignKey("chunks.id", ondelete="CASCADE"), primary_key=True)
    asset_id = Column(UUID(as_uuid=True), ForeignKey("document_assets.id", ondelete="CASCADE"), primary_key=True)


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
    role = Column(String(50), nullable=False, default="standard")


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
    weight = Column(Integer, nullable=False, default=1)


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
    answer = Column(Text)
    sources_used = Column(JSON, default=list) # [{doc_id: ..., chunk_id: ..., score: ...}]
    edges_used = Column(JSON, default=list) # [relation_id_1, relation_id_2, ...]
    result_count = Column(Integer, default=0)
    feedback = Column(Integer, default=0) # 1: 👍, -1: 👎, 0: none
    feedback_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


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


class AIWorkflowORM(Base):
    __tablename__ = "ai_workflows"
    __table_args__ = {"comment": "AI workflows defining multi-step prompt chains"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=False, default="")
    trigger_type = Column(String(50), nullable=False, default="manual")  # manual | scheduled | webhook
    schedule_cron = Column(String(100), nullable=True)  # e.g. '0 8 * * 1-5' for weekdays at 8am
    webhook_token = Column(String(100), nullable=True, unique=True)  # for webhook trigger
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_by = Column(String(255), nullable=False, default="system")


class AIWorkflowNodeORM(Base):
    __tablename__ = "ai_workflow_nodes"
    __table_args__ = {"comment": "Individual steps in an AI workflow"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("ai_workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    step_order = Column(Integer, nullable=False)
    name = Column(String(255), nullable=False)
    node_type = Column(String(50), nullable=False, default="llm")  # llm | rag | doc_writer
    model_override = Column(String(100), nullable=True)
    system_prompt = Column(Text, nullable=False, default="")
    input_vars = Column(JSON, default=list)  # list of variable names this node expects
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class WorkflowRunORM(Base):
    __tablename__ = "workflow_runs"
    __table_args__ = {"comment": "Execution history for AI workflow runs"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id = Column(UUID(as_uuid=True), ForeignKey("ai_workflows.id", ondelete="CASCADE"), nullable=False, index=True)
    job_id = Column(UUID(as_uuid=True), nullable=True)  # link to ChatJob
    triggered_by = Column(String(255), nullable=True)  # user_id or 'scheduler' or 'webhook'
    trigger_type = Column(String(50), nullable=False, default="manual")
    status = Column(String(20), nullable=False, default="queued")  # queued|running|completed|failed
    initial_context = Column(Text, nullable=True)
    node_outputs = Column(JSON, default=dict)  # {"node_1": "...", "node_2": "..."}
    final_output = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class SkillPromptORM(Base):
    __tablename__ = "skill_prompts"

    doc_type = Column(String(80), primary_key=True)
    label = Column(Text, nullable=False, default="")
    description = Column(Text, nullable=False, default="")
    system_prompt = Column(Text, nullable=False, default="")
    group = Column(String(100), nullable=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_by = Column(String(255), nullable=False, default="system")


class SDLCJobORM(Base):
    __tablename__ = "sdlc_jobs"
    __table_args__ = {"comment": "Tracks Multi-Agent SDLC pipeline jobs"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), index=True)
    request = Column(Text, nullable=False)
    context = Column(Text)
    status = Column(String(20), nullable=False, default="processing")  # processing, completed, failed
    result = Column(JSON)  # stores the final SDLCState
    error = Column(Text)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class LLMModelORM(Base):
    __tablename__ = "llm_models"
    __table_args__ = {"comment": "Registry for managed LLM models and providers"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    provider = Column(String(50), nullable=False) # gemini, openai, ollama, vllm
    llm_model_name = Column(String(255), nullable=False) # technical name
    base_url = Column(Text) # for self-hosted providers
    api_key = Column(Text) # optional, for remote providers
    is_active = Column(Boolean, nullable=False, default=True)
    is_default = Column(Boolean, nullable=False, default=False)
    is_chat_enabled = Column(Boolean, nullable=False, default=False) # Whether users can select this in chat
    description = Column(Text) # Purpose/Usage of this model
    config = Column(JSON, default={}) # temperature, top_p, etc.
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class ModelBindingORM(Base):
    __tablename__ = "model_bindings"
    __table_args__ = {"comment": "Maps specific tasks to specific models (e.g. chat, ingestion, embedding)"}

    task_type = Column(String(50), primary_key=True) # chat, ingestion_llm, agent, embedding
    model_id = Column(UUID(as_uuid=True), ForeignKey("llm_models.id", ondelete="CASCADE"), nullable=False)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class PMMetricsDailyORM(Base):
    __tablename__ = "pm_metrics_daily"
    __table_args__ = (
        Index("ix_pm_metrics_daily_lookup", "date", "project_key"),
        {"comment": "Pre-aggregated daily snapshots of project status counts"}
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date = Column(DateTime, nullable=False)
    project_key = Column(String(50), nullable=False)
    todo_count = Column(Integer, default=0)
    in_progress_count = Column(Integer, default=0)
    done_count = Column(Integer, default=0)
    high_priority_count = Column(Integer, default=0)
    avg_lead_time_days = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

class PMMetricsByUserORM(Base):
    __tablename__ = "pm_metrics_by_user"
    __table_args__ = (
        Index("ix_pm_metrics_user_lookup", "user_id", "project_key"),
        {"comment": "Per-user workload and stale task metrics"}
    )
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False) # Jira accountId or name
    display_name = Column(String(255))
    project_key = Column(String(50), nullable=False)
    todo_count = Column(Integer, default=0)
    in_progress_count = Column(Integer, default=0)
    done_count = Column(Integer, default=0)
    stale_count = Column(Integer, default=0) # WIP but no update > 3 days
    updated_at = Column(DateTime, default=datetime.utcnow)

class PMMetricsByProjectORM(Base):
    __tablename__ = "pm_metrics_by_project"
    __table_args__ = {"comment": "High-level project health and velocity trends"}
    project_key = Column(String(50), primary_key=True)
    velocity_weekly = Column(Float, default=0.0) # items per week
    velocity_delta_pct = Column(Float, default=0.0) # comparison with prev week
    risk_score = Column(Float, default=0.0) # 0-100
    health_status = Column(String(20), default="healthy") # healthy, warning, critical
    insight = Column(Text) # Bottleneck/Velocity alerts
    updated_at = Column(DateTime, default=datetime.utcnow)


class SMTPSettingsORM(Base):
    __tablename__ = "smtp_settings"
    __table_args__ = {"comment": "System-wide SMTP configuration for sending emails"}

    id = Column(String(50), primary_key=True, default="default")
    smtp_host = Column(String(255))
    smtp_port = Column(Integer)
    security_mode = Column(String(20), default="STARTTLS") # NONE, SSL, STARTTLS
    authentication_enabled = Column(Boolean, default=False)
    smtp_username = Column(String(255))
    smtp_password = Column(String(255))
    sender_email_address = Column(String(255))
    sender_display_name = Column(String(255))
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class UserMappingORM(Base):
    __tablename__ = "user_mappings"
    __table_args__ = {"comment": "Maps internal users to external system identities (e.g. Jira)"}

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    system_name = Column(String(50), nullable=False, default="jira") # e.g. 'jira'
    external_id = Column(String(255), nullable=False) # e.g. Jira username or accountId
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


from contextlib import contextmanager

@contextmanager
def get_sync_db():
    session = SyncSessionLocal()
    try:
        yield session
    finally:
        session.close()


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(text(
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS workspace_id VARCHAR(255)"
        ))
        await conn.execute(text(
            "ALTER TABLE documents ADD COLUMN IF NOT EXISTS summary TEXT"
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
            "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) NOT NULL DEFAULT 'standard'"
        ))
        await conn.execute(text(
            "ALTER TABLE users ALTER COLUMN role SET DEFAULT 'standard'"
        ))
        await conn.execute(text(
            "UPDATE users SET role = 'standard' WHERE role IS NULL OR role = ''"
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
        await conn.execute(text(
            "ALTER TABLE entity_relations ADD COLUMN IF NOT EXISTS weight INTEGER NOT NULL DEFAULT 1"
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
                parent_draft_id UUID REFERENCES ai_task_drafts(id) ON DELETE CASCADE,
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
            "ALTER TABLE ai_task_drafts ADD COLUMN IF NOT EXISTS parent_draft_id UUID REFERENCES ai_task_drafts(id) ON DELETE CASCADE"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_ai_task_drafts_dedup_key ON ai_task_drafts (dedup_key)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_ai_task_drafts_scope_group_id ON ai_task_drafts (scope_group_id)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_ai_task_drafts_parent_draft_id ON ai_task_drafts (parent_draft_id)"
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

        # Assets: store images (and future media) linked to documents/chunks.
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS document_assets (
                    id UUID PRIMARY KEY,
                    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
                    source VARCHAR(50) NOT NULL,
                    source_ref TEXT,
                    kind VARCHAR(20) NOT NULL DEFAULT 'image',
                    filename TEXT,
                    mime_type VARCHAR(100),
                    bytes INTEGER,
                    sha256 VARCHAR(64),
                    local_path TEXT NOT NULL,
                    caption TEXT,
                    ocr_text TEXT,
                    width INTEGER,
                    height INTEGER,
                    meta JSON NOT NULL DEFAULT '{}'::json,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
                """
            )
        )
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_document_assets_document_id ON document_assets (document_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_document_assets_sha256 ON document_assets (sha256)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_document_assets_source ON document_assets (source)"))

        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS chunk_assets (
                    chunk_id UUID NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
                    asset_id UUID NOT NULL REFERENCES document_assets(id) ON DELETE CASCADE,
                    PRIMARY KEY (chunk_id, asset_id)
                )
                """
            )
        )
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chunk_assets_chunk_id ON chunk_assets (chunk_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_chunk_assets_asset_id ON chunk_assets (asset_id)"))

        # ── Skill Prompts: editable BA agent system instructions ──────────────
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS skill_prompts (
                doc_type      VARCHAR(80)  PRIMARY KEY,
                label         TEXT         NOT NULL DEFAULT '',
                description   TEXT         NOT NULL DEFAULT '',
                system_prompt TEXT         NOT NULL DEFAULT '',
                updated_at    TIMESTAMP    NOT NULL DEFAULT NOW(),
                updated_by    VARCHAR(255) NOT NULL DEFAULT 'system'
            )
        """))
        await conn.execute(text(
            "ALTER TABLE skill_prompts ADD COLUMN IF NOT EXISTS \"group\" VARCHAR(100)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_skill_prompts_doc_type ON skill_prompts (doc_type)"
        ))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS project_memories (
                id UUID PRIMARY KEY,
                memory_type VARCHAR(50) NOT NULL,
                key VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                created_by VARCHAR(255),
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                UNIQUE (memory_type, key)
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_project_memories_type_key ON project_memories (memory_type, key)"
        ))

        # ── AI Workflows ──────────────
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ai_workflows (
                id UUID PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                trigger_type VARCHAR(50) NOT NULL DEFAULT 'manual',
                schedule_cron VARCHAR(100),
                webhook_token VARCHAR(100) UNIQUE,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_by VARCHAR(255) NOT NULL DEFAULT 'system'
            )
        """))
        await conn.execute(text("ALTER TABLE ai_workflows ADD COLUMN IF NOT EXISTS schedule_cron VARCHAR(100)"))
        await conn.execute(text("ALTER TABLE ai_workflows ADD COLUMN IF NOT EXISTS webhook_token VARCHAR(100) UNIQUE"))
        
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS ai_workflow_nodes (
                id UUID PRIMARY KEY,
                workflow_id UUID NOT NULL REFERENCES ai_workflows(id) ON DELETE CASCADE,
                step_order INTEGER NOT NULL,
                name VARCHAR(255) NOT NULL,
                node_type VARCHAR(50) NOT NULL DEFAULT 'llm',
                model_override VARCHAR(100),
                system_prompt TEXT NOT NULL DEFAULT '',
                input_vars JSON NOT NULL DEFAULT '[]'::json,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("ALTER TABLE ai_workflow_nodes ADD COLUMN IF NOT EXISTS node_type VARCHAR(50) NOT NULL DEFAULT 'llm'"))
        await conn.execute(text("ALTER TABLE ai_workflow_nodes ADD COLUMN IF NOT EXISTS input_vars JSON NOT NULL DEFAULT '[]'::json"))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_workflow_nodes_workflow_id ON ai_workflow_nodes (workflow_id)"
        ))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS workflow_runs (
                id UUID PRIMARY KEY,
                workflow_id UUID NOT NULL REFERENCES ai_workflows(id) ON DELETE CASCADE,
                job_id UUID,
                triggered_by VARCHAR(255),
                trigger_type VARCHAR(50) NOT NULL DEFAULT 'manual',
                status VARCHAR(20) NOT NULL DEFAULT 'queued',
                initial_context TEXT,
                node_outputs JSON NOT NULL DEFAULT '{}'::json,
                final_output TEXT,
                error TEXT,
                started_at TIMESTAMP,
                finished_at TIMESTAMP,
                created_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_workflow_runs_workflow_id ON workflow_runs (workflow_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS idx_workflow_runs_status ON workflow_runs (status)"))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS sdlc_jobs (
                id UUID PRIMARY KEY,
                user_id VARCHAR(255),
                request TEXT NOT NULL,
                context TEXT,
                status VARCHAR(20) NOT NULL DEFAULT 'processing',
                result JSON,
                error TEXT,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_sdlc_jobs_user_id ON sdlc_jobs (user_id)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_sdlc_jobs_status ON sdlc_jobs (status)"
        ))
        
        # Query Logs Migration for Feedback Loop
        await conn.execute(text("ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS answer TEXT"))
        await conn.execute(text("ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS sources_used JSON NOT NULL DEFAULT '[]'::json"))
        await conn.execute(text("ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS edges_used JSON NOT NULL DEFAULT '[]'::json"))
        await conn.execute(text("ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS feedback INTEGER NOT NULL DEFAULT 0"))
        await conn.execute(text("ALTER TABLE query_logs ADD COLUMN IF NOT EXISTS feedback_at TIMESTAMP"))
        await conn.execute(text("ALTER TABLE query_logs ALTER COLUMN created_at SET DEFAULT NOW()"))
        
        # Chat Messages Migration for Feedback Loop
        await conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS query_id VARCHAR(36)"))
        await conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS sources JSONB NOT NULL DEFAULT '[]'::jsonb"))
        await conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS agent_plan JSONB NOT NULL DEFAULT '[]'::jsonb"))
        await conn.execute(text("ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS rewritten_query TEXT"))

        # ── LLM Models Migration ──────────────
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS llm_models (
                id UUID PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                provider VARCHAR(50) NOT NULL,
                llm_model_name VARCHAR(255) NOT NULL,
                base_url TEXT,
                api_key TEXT,
                is_active BOOLEAN NOT NULL DEFAULT TRUE,
                is_default BOOLEAN NOT NULL DEFAULT FALSE,
                is_chat_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                config JSON NOT NULL DEFAULT '{}'::json,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_llm_models_provider ON llm_models (provider)"
        ))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_llm_models_is_default ON llm_models (is_default)"
        ))
        await conn.execute(text(
            "ALTER TABLE llm_models ADD COLUMN IF NOT EXISTS description TEXT"
        ))
        await conn.execute(text(
            "ALTER TABLE llm_models ADD COLUMN IF NOT EXISTS is_default BOOLEAN NOT NULL DEFAULT FALSE"
        ))
        await conn.execute(text(
            "ALTER TABLE llm_models ADD COLUMN IF NOT EXISTS base_url TEXT"
        ))
        await conn.execute(text(
            "ALTER TABLE llm_models ADD COLUMN IF NOT EXISTS api_key TEXT"
        ))
        await conn.execute(text(
            "ALTER TABLE llm_models ADD COLUMN IF NOT EXISTS llm_model_name VARCHAR(255) NOT NULL DEFAULT 'unknown'"
        ))
        await conn.execute(text(
            "ALTER TABLE llm_models ADD COLUMN IF NOT EXISTS is_chat_enabled BOOLEAN NOT NULL DEFAULT FALSE"
        ))
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS model_bindings (
                task_type VARCHAR(50) PRIMARY KEY,
                model_id UUID NOT NULL REFERENCES llm_models(id) ON DELETE CASCADE,
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS smtp_settings (
                id VARCHAR(50) PRIMARY KEY DEFAULT 'default',
                smtp_host VARCHAR(255),
                smtp_port INTEGER,
                security_mode VARCHAR(20) DEFAULT 'STARTTLS',
                authentication_enabled BOOLEAN DEFAULT FALSE,
                smtp_username VARCHAR(255),
                smtp_password VARCHAR(255),
                sender_email_address VARCHAR(255),
                sender_display_name VARCHAR(255),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))

        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_mappings (
                id UUID PRIMARY KEY,
                user_id VARCHAR(255) NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                system_name VARCHAR(50) NOT NULL DEFAULT 'jira',
                external_id VARCHAR(255) NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP NOT NULL DEFAULT NOW()
            )
        """))
        await conn.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_user_mappings_user_id ON user_mappings (user_id)"
        ))
        await conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_user_mappings_system_external ON user_mappings (system_name, external_id)"
        ))

async def reset_llm_models_to_defaults():
    """Xóa sạch và nạp lại cấu hình model chuẩn từ settings."""
    import uuid
    import structlog
    from sqlalchemy import select, func, delete
    from config.settings import settings

    async with AsyncSessionLocal() as session:
        # 0. Manual Schema Sync (Raw SQL) to fix ProgrammingError for missing columns
        from sqlalchemy import text
        await session.execute(text("ALTER TABLE llm_models ADD COLUMN IF NOT EXISTS description TEXT"))
        await session.execute(text("ALTER TABLE llm_models ADD COLUMN IF NOT EXISTS is_default BOOLEAN NOT NULL DEFAULT FALSE"))
        await session.execute(text("ALTER TABLE llm_models ADD COLUMN IF NOT EXISTS base_url TEXT"))
        await session.execute(text("ALTER TABLE llm_models ADD COLUMN IF NOT EXISTS api_key TEXT"))
        await session.execute(text("ALTER TABLE llm_models ADD COLUMN IF NOT EXISTS llm_model_name VARCHAR(255) NOT NULL DEFAULT 'unknown'"))
        await session.execute(text("ALTER TABLE llm_models ADD COLUMN IF NOT EXISTS is_chat_enabled BOOLEAN NOT NULL DEFAULT FALSE"))
        await session.commit()

        # 1. Clear everything
        # Note: ModelBindingORM refers to model_bindings table, LLMModelORM to llm_models
        await session.execute(delete(ModelBindingORM))
        await session.execute(delete(LLMModelORM))
        await session.commit()
        
        # 2. Seed Models
        models_to_seed = [
            {
                "id": uuid.uuid4(),
                "name": "Ollama LLM (Primary)",
                "provider": "ollama",
                "llm_model_name": settings.OLLAMA_LLM_MODEL,
                "description": f"Mô hình ngôn ngữ chính ({settings.OLLAMA_LLM_MODEL}) chạy nội bộ",
                "base_url": settings.OLLAMA_BASE_URL,
                "is_active": True,
                "is_default": True,
                "is_chat_enabled": True
            },
            {
                "id": uuid.uuid4(),
                "name": "Ollama Embedding",
                "provider": "ollama",
                "llm_model_name": settings.OLLAMA_EMBED_MODEL,
                "description": f"Mô hình nhúng văn bản ({settings.OLLAMA_EMBED_MODEL})",
                "base_url": settings.OLLAMA_BASE_URL,
                "is_active": True,
                "is_default": False
            },
            {
                "id": uuid.uuid4(),
                "name": "Ollama Vision",
                "provider": "ollama",
                "llm_model_name": settings.OLLAMA_VISION_MODEL or "llava-phi3",
                "description": f"Mô hình thị giác máy tính ({settings.OLLAMA_VISION_MODEL or 'llava-phi3'})",
                "base_url": settings.OLLAMA_BASE_URL,
                "is_active": True,
                "is_default": False
            }
        ]
        for m in models_to_seed:
            session.add(LLMModelORM(**m))
        await session.commit()

        # 3. Seed Bindings
        res = await session.execute(select(LLMModelORM).where(LLMModelORM.name == "Ollama LLM (Primary)").limit(1))
        primary_llm = res.scalar_one_or_none()
        res_embed = await session.execute(select(LLMModelORM).where(LLMModelORM.name == "Ollama Embedding").limit(1))
        embed_llm = res_embed.scalar_one_or_none()
        res_vision = await session.execute(select(LLMModelORM).where(LLMModelORM.name == "Ollama Vision").limit(1))
        vision_llm = res_vision.scalar_one_or_none()

        if primary_llm:
            bindings = [
                {"task_type": "chat", "model_id": primary_llm.id},
                {"task_type": "ingestion_llm", "model_id": primary_llm.id},
                {"task_type": "agent", "model_id": primary_llm.id},
                {"task_type": "skill", "model_id": primary_llm.id},
            ]
            if embed_llm:
                bindings.append({"task_type": "embedding", "model_id": embed_llm.id})
            if vision_llm:
                bindings.append({"task_type": "vision", "model_id": vision_llm.id})
            
            for b in bindings:
                session.add(ModelBindingORM(**b))
            await session.commit()
        
        structlog.get_logger().info("llm_models.reset_to_defaults", count=len(models_to_seed))

async def initial_db_setup():
    """Thiết lập ban đầu cho Database (Tables, Indexes, Seed Data)."""
    await create_tables()

    # Seed default LLM models if table is empty or has old logic
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select, func
        result = await session.execute(select(func.count()).select_from(LLMModelORM))
        count = result.scalar()
        
        res_legacy = await session.execute(
            select(LLMModelORM).where(
                (LLMModelORM.name.like('%Gemini%')) | 
                (LLMModelORM.name.like('%Ollama Default%'))
            ).limit(1)
        )
        has_legacy = res_legacy.scalar_one_or_none() is not None
        
        if count == 0 or has_legacy:
            await reset_llm_models_to_defaults()

    # Seed default prompts (only inserts rows that don't exist yet)
    async with AsyncSessionLocal() as session:
        from persistence.skill_prompt_repository import SkillPromptRepository
        repo = SkillPromptRepository(session)
        seeded = await repo.seed_defaults()
        if seeded:
            import structlog
            structlog.get_logger().info("skill_prompts.seeded", count=seeded)
