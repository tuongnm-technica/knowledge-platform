from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Knowledge Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/knowledge_platform"
    DATABASE_SYNC_URL: str = "postgresql://postgres:postgres@localhost:5432/knowledge_platform"

    REDIS_URL: str = "redis://localhost:6379/0"
    RUN_WORKER: bool = False

    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "knowledge_chunks"
    QDRANT_API_KEY: Optional[str] = None

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_LLM_MODEL: str = "qwen2.5:7b"
    OLLAMA_EMBED_MODEL: str = "bge-m3"
    EMBEDDING_MODEL: str = OLLAMA_EMBED_MODEL
    LLM_TIMEOUT: int = 800
    VECTOR_DIM: int = 1024

    HYBRID_ALPHA: float = 0.5
    BM25_WEIGHT: float = 0.3
    GRAPH_WEIGHT: float = 0.2
    RECENCY_WEIGHT: float = 0.1
    POPULARITY_WEIGHT: float = 0.1
    TOP_K: int = 10
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50

    QUERY_EXPANSION_ENABLED: bool = True
    RERANKING_ENABLED: bool = True
    # none | llm | cross_encoder
    RERANKER_BACKEND: str = "llm"
    # Used when RERANKER_BACKEND=cross_encoder (HuggingFace model id or local path).
    CROSS_ENCODER_MODEL: str = "BAAI/bge-reranker-base"
    CROSS_ENCODER_DEVICE: str = "cpu"
    SEMANTIC_CACHE_ENABLED: bool = True

    SLACK_BOT_TOKEN: Optional[str] = None
    CONFLUENCE_URL: Optional[str] = None
    CONFLUENCE_USERNAME: Optional[str] = None
    CONFLUENCE_API_TOKEN: Optional[str] = None
    CONFLUENCE_SPACE_KEYS: str = ""
    CONFLUENCE_VERIFY_TLS: bool = True
    JIRA_URL: Optional[str] = None
    JIRA_USERNAME: Optional[str] = None
    JIRA_API_TOKEN: Optional[str] = None
    JIRA_PROJECT_KEYS: str = ""
    JIRA_VERIFY_TLS: bool = True
    DEFAULT_JIRA_PROJECT: str = ""

    SMB_HOST: Optional[str] = None
    SMB_USERNAME: Optional[str] = None
    SMB_PASSWORD: Optional[str] = None
    SMB_SHARE: Optional[str] = None
    SMB_BASE_PATH: str = ""

    DEFAULT_WORKSPACE: str = "ws_general"
    CONFLUENCE_WORKSPACE_MAP: str = ""
    JIRA_WORKSPACE_MAP: str = ""
    SLACK_WORKSPACE_MAP: str = ""
    SMB_WORKSPACE_MAP: str = ""

    JWT_SECRET: str = "change-me-in-production"
    JWT_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_DAYS: int = 7

    PUBLIC_API_BASE_URL: Optional[str] = None

    # Local asset storage (images, extracted diagrams, screenshots, etc.)
    ASSETS_DIR: str = "assets"
    ASSETS_MAX_BYTES: int = 8_000_000  # 8MB per asset

    # Vision pipeline (caption/OCR + multimodal context)
    VISION_ENABLED: bool = False
    OLLAMA_VISION_MODEL: Optional[str] = "llava-phi3"  # must be installed in Ollama
    VISION_MAX_IMAGES_PER_DOC: int = 8
    VISION_MAX_IMAGES_PER_CHUNK: int = 3
    VISION_MAX_IMAGES_PER_ANSWER: int = 2
    VISION_CAPTION_MAX_CHARS: int = 900

    AGENT_MAX_STEPS: int = 5

    AGENT_SELF_CORRECT_ENABLED: bool = True
    AGENT_LOGIC_CHECK_ENABLED: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
