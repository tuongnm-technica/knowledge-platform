from typing import Optional
import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Knowledge Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/knowledge_platform")
    DATABASE_SYNC_URL: str = os.getenv("DATABASE_SYNC_URL", "postgresql://postgres:password@localhost:5432/knowledge_platform")

    # Default to 'redis' for docker, will be overridden by .env or ENV VAR
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://redis:6379/0")
    RUN_WORKER: bool = False

    # ── ARQ Queue & Worker Settings ──
    ARQ_DEFAULT_QUEUE_NAME: str = "arq:default"
    ARQ_DEFAULT_MAX_JOBS: int = 10
    ARQ_DEFAULT_JOB_TIMEOUT: int = 120

    ARQ_INGESTION_QUEUE_NAME: str = "arq:ingestion"
    ARQ_INGESTION_MAX_JOBS: int = 2
    ARQ_INGESTION_JOB_TIMEOUT: int = 1200

    ARQ_AI_QUEUE_NAME: str = "arq:ai"

    QDRANT_HOST: str = "qdrant"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION: str = "knowledge_chunks"
    QDRANT_API_KEY: Optional[str] = None

    OLLAMA_BASE_URL: str = "http://host.docker.internal:11434"
    OLLAMA_LLM_MODEL: str = "qwen2.5:14b"
    OLLAMA_EMBED_MODEL: str = "bge-m3"

    LLM_PROVIDER: str = "ollama"  # ollama | vllm | openai
    INFERENCE_BASE_URL: Optional[str] = None # For vLLM/OpenAI compatible services
    RAG_SERVICE_URL: str = "http://localhost:8001"

    EMBEDDING_MODEL: str = OLLAMA_EMBED_MODEL
    EMBEDDING_CONCURRENCY: int = 2  # Concurrency limit for embedding API calls
    LLM_TIMEOUT: int = 900
    ARQ_AI_JOB_TIMEOUT: int = 1500
    VECTOR_DIM: int = 1024
    
    # Ingestion batch size: process documents in smaller batches to prevent timeout
    INGESTION_BATCH_SIZE: int = 10

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
    SEMANTIC_CACHE_THRESHOLD: float = 0.92

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
    AGENT_REACT_TIMEOUT: int = 900
    AGENT_MAX_PLAN_STEPS: int = 3
    FRONTEND_POLLING_INTERVAL_MS: int = 5000

    AGENT_SELF_CORRECT_ENABLED: bool = True
    AGENT_LOGIC_CHECK_ENABLED: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        # Ensure environment variables always take precedence over .env file
        env_nested_delimiter = '__'


settings = Settings()
