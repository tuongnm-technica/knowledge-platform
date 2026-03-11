"""
On-Premise Database — PostgreSQL
──────────────────────────────────
All metadata stored in PostgreSQL (on-premise).
Vector embeddings stored in Qdrant (separate on-premise container).

No pgvector extension required.
"""

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import (
    Column, String, Text, DateTime, JSON, ARRAY, Integer, ForeignKey, BigInteger
)
from sqlalchemy.dialects.postgresql import UUID
from config.settings import settings
import uuid


engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG, pool_size=10)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


# ─── ORM Models ──────────────────────────────────────────────────────────────

class DocumentORM(Base):
    __tablename__ = "documents"
    __table_args__ = {"comment": "Core knowledge units ingested from external systems"}

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



class SyncLogORM(Base):
    __tablename__ = "sync_logs"
    __table_args__ = {"comment": "Track incremental sync state per connector"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    connector = Column(String(50), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="running")  # running|success|partial|failed
    started_at = Column(DateTime)
    finished_at = Column(DateTime)
    last_sync_at = Column(DateTime, index=True)
    fetched = Column(Integer, default=0)
    indexed = Column(Integer, default=0)
    errors = Column(Integer, default=0)

# ─── Session Helper ──────────────────────────────────────────────────────────

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Create GIN index for PostgreSQL full-text search on chunks
    async with AsyncSessionLocal() as session:
        await session.execute(__import__('sqlalchemy').text(
            "CREATE INDEX IF NOT EXISTS idx_chunks_fts "
            "ON chunks USING GIN (to_tsvector('english', content))"
        ))
        await session.commit()