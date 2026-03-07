from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import (
    Column, String, Text, DateTime, JSON, ARRAY, Integer, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID
from config.settings import settings
import uuid


engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG, pool_size=10)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class DocumentORM(Base):
    __tablename__ = "documents"

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


class DocumentSummaryORM(Base):
    __tablename__ = "document_summaries"

    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    summary = Column(Text, nullable=False)


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        from sqlalchemy import text
        await session.execute(text(
            "CREATE INDEX IF NOT EXISTS idx_chunks_fts "
            "ON chunks USING GIN (to_tsvector('english', content))"
        ))
        await session.commit()