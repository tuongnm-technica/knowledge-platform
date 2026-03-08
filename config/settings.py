from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # ─── App ──────────────────────────────────────────────────────────────────
    APP_NAME: str = "Knowledge Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    # ─── PostgreSQL (on-premise) ───────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/knowledge_platform"
    DATABASE_SYNC_URL: str = "postgresql://postgres:postgres@localhost:5432/knowledge_platform"

    # ─── Qdrant Vector DB (on-premise Docker) ─────────────────────────────────
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "knowledge_chunks"
    QDRANT_API_KEY: Optional[str] = None

    # ─── Embedding: Local sentence-transformers ────────────────────────────────
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    VECTOR_DIM: int = 384

    # ─── LLM: Ollama (on-premise) ─────────────────────────────────────────────
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = "llama3"
    LLM_TIMEOUT: int = 120

    # ─── Search weights ────────────────────────────────────────────────────────
    HYBRID_ALPHA: float = 0.5
    BM25_WEIGHT: float = 0.3
    RECENCY_WEIGHT: float = 0.1
    POPULARITY_WEIGHT: float = 0.1
    TOP_K: int = 10
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50

    # ─── Connectors ────────────────────────────────────────────────────────────
    SLACK_BOT_TOKEN: Optional[str] = None
    CONFLUENCE_URL: Optional[str] = None
    # CONFLUENCE_USERNAME: Optional[str] = None
    CONFLUENCE_API_TOKEN: Optional[str] = None
    JIRA_URL: Optional[str] = None
    # JIRA_USERNAME: Optional[str] = None
    JIRA_API_TOKEN: Optional[str] = None

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()