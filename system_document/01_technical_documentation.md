# Tài liệu Kỹ thuật — Knowledge Platform

> [!CAUTION]
> Các tệp tin `.docx` và `.pptx` trong thư mục này đã **lỗi thời**. Vui lòng chỉ tham khảo các tệp tin `.md` cập nhật.

> **Phiên bản tài liệu:** 2.1 (Hardened for 30 Users) | **Ngày cập nhật:** 2026-04-03  
> **Trạng thái hệ thống:** Đang phát biểu — Internal / Pre-production

---

## 1. Tổng quan

Knowledge Platform là công cụ nội bộ phục vụ hai mục tiêu:
1. **RAG-based Q&A** — tìm kiếm và trả lời câu hỏi dựa trên kho tài liệu nội bộ.
2. **SDLC Document Automation** — tự động điều phối chuỗi 9 AI agent để soạn thảo tài liệu phần mềm.

---

## 2. Stack công nghệ

### 2.1 Backend

| Thành phần | Thư viện / Công cụ | Chi tiết |
|---|---|---|
| API Framework | FastAPI | Python async, port 8000 |
| ORM (async) | SQLAlchemy + asyncpg | **Pool Size: 30**, Max Overflow: 10, Async session cho mọi route |
| ORM (sync) | SQLAlchemy + psycopg2 | Dùng trong scheduler và script |
| Migrations | Alembic | Schema versioning |
| Database | PostgreSQL | Chạy **local**, không có trong docker-compose |
| Vector Store | Qdrant | Port 6333, persistent volume |
| Message Queue | Redis 7 Alpine | Port 6379 |
| Background Jobs | arq | 3 queue riêng biệt: `default`, `ingestion`, `ai` |
| Scheduler | APScheduler (sync) | Chạy cùng API process |
| Embedding | Ollama `/api/embed` | Model `bge-m3`, dim 1024, concurrency 5 |
| LLM | Ollama / vLLM / OpenAI | Managed qua `llm_models` registry, model `qwen2.5:14b` mặc định |
| Keyword Search | rank-bm25 | In-process, không phải service riêng |
| Graph | networkx + PostgreSQL | networkx trong bộ nhớ, entity lưu vào PG |
| Logging | structlog | JSON-format structured logging |
| Auth | PyJWT + bcrypt | JWT tự implement |
| Connectors | Jira, Confluence, Slack, SMB, **Zoom, Drive** | Tích hợp đa nguồn |
| Document Export | Node.js Bridge (`docx`, `pptxgenjs`) | Xuất file Word/Slide cao cấp |
| Email Service | aiosmtplib | SMTP với hỗ trợ file đính kèm |

### 2.2 Frontend

| Thành phần | Công nghệ | Chi tiết |
|---|---|---|
| Language | TypeScript | Compile với Vite |
| Router | Navigo | Client-side SPA HTML5 History API |
| CSS | Vanilla CSS | Không dùng framework |
| Build output | `web/dist/` | Được serve bởi FastAPI static hoặc nginx |
| Serve (Docker) | nginx | Port 3000 |
| Serve (Local dev) | FastAPI static mount | Port 8000, cùng API server |

### 2.3 Infrastructure (Docker Compose)

```
Services:
├── redis            redis:7-alpine          port 6379
├── qdrant           qdrant/qdrant:latest    port 6333 (volume: qdrant_data)
├── api              kp image                port 8000   python run.py
├── rag_service      kp image                port 8001   uvicorn orchestration.main:app
├── worker_ingestion kp image                            ARQ_WORKER_TYPE=ingestion
├── worker_default   kp image                            ARQ_WORKER_TYPE=default
├── worker_ai        kp image                            ARQ_WORKER_TYPE=ai
└── web              nginx                   port 3000   serve web/dist/
```

> ⚠️ PostgreSQL **không** có trong docker-compose. DB chạy local trên máy host, các container kết nối qua `host.docker.internal`.

---

## 3. Cấu trúc thư mục (đầy đủ)

```
knowledge-platform/
├── apps/
│   └── api/
│       ├── server.py              # FastAPI app, lifespan, CORS, route registration, SDLC proxy
│       ├── auth/
│       │   ├── dependencies.py    # get_current_user, require_admin, require_task_manager, RBAC
│       │   └── jwt_handler.py     # decode/encode JWT
│       └── routes/                # 20 route files (ask, search, docs, graph, users, tasks...)
├── orchestration/
│   ├── main.py                    # rag_service FastAPI app (port 8001)
│   ├── agent.py                   # Agent + InferenceClient (OpenAI-compatible)
│   ├── react_loop.py              # ReActLoop: Planner+Executor (635 lines)
│   ├── agent_workflow.py          # Multi-agent workflow orchestration
│   ├── agent_tasks.py             # arq task definitions cho SDLC workflow
│   ├── doc_orchestrator.py        # Orchestrator cho document drafting
│   ├── sdlc_tasks.py              # SDLC-specific task defs
│   └── tools/                     # Tool registry (search_all, graph_query...)
├── services/
│   ├── rag_service.py             # RAGService: 8-bước pipeline (333 lines)
│   ├── context_builder.py         # ContextBuilder: filter+group+dedup+tokenbudget
│   ├── embedding_service.py       # EmbeddingService: batch embedding với cache
│   └── llm_service.py             # LLMService: wrapper gọi InferenceClient
├── retrieval/
│   ├── hybrid/hybrid_search.py    # HybridSearch: kết hợp vector + keyword
│   ├── vector/                    # Vector search (Qdrant)
│   ├── keyword/                   # Keyword search (BM25)
│   ├── reranker.py                # Reranker: LLM-mode + Cross-Encoder mode
│   ├── context_compressor.py      # Nén context trước khi đưa vào LLM
│   ├── semantic_cache.py          # Semantic cache lookup/store (Qdrant)
│   ├── query_expansion.py         # Mở rộng query bằng LLM
│   └── query_router.py            # Định tuyến query tới retrieval strategy
├── ranking/
│   ├── scorer.py                  # RankingScorer: 5 signal scoring
│   └── signals.py                 # semantic, keyword, graph, recency, popularity signals
├── graph/
│   ├── knowledge_graph.py         # KnowledgeGraph: entity+identity upsert, 2-hop traversal
│   ├── entity_extractor.py        # EntityExtractor: NER (name, tech, project...)
│   ├── identity_resolver.py       # IdentityResolver: merge người dùng qua aliases
│   ├── document_linker.py         # DocumentLinker: cross-doc link extraction
│   └── graph_view.py              # Graph view API cho frontend (51KB)
├── ingestion/
│   ├── pipeline.py                # IngestionPipeline: 6-bước orchestration
│   ├── chunker.py / chunker_factory.py / chunkers/  # Chunking strategies
│   ├── cleaner.py                 # TextCleaner
│   ├── metadata_extractor.py      # MetadataExtractor
│   └── assets_ingestor.py         # AssetIngestor: download, OCR/caption hình ảnh
├── connectors/
│   ├── base/base_connector.py     # BaseConnector interface
│   ├── jira/                      # Jira connector (fetch issues, comments)
│   ├── confluence/                # Confluence connector (fetch pages, parse HTML)
│   ├── slack/                     # Slack connector (fetch messages, deep links)
│   └── fileserver/                # SMB File Server connector
├── tasks/                         # AI Task Drafts module (Jira integration)
│   ├── routes.py                  # REST routes (461 lines)
│   ├── repository.py              # TaskDraftRepository
│   ├── models.py                  # TaskDraft model
│   ├── task_writer.py             # Build task from RAG answer
│   ├── scanner.py                 # Scan Slack/Confluence for task signals
│   ├── jira_creator.py            # Submit draft to Jira API
│   ├── jira_sync.py               # Sync Jira status về DB
│   ├── grouping.py                # Group related drafts
│   └── extractor.py               # Extract task details từ content
├── persistence/                   # Repository pattern cho từng entity
│   ├── document_repository.py     # Documents, chunks, section queries
│   ├── doc_draft_repository.py    # AI document drafts
│   ├── project_memory_repository.py  # Glossary, actor, rule memory
│   ├── skill_prompt_repository.py # Custom skill prompts
│   ├── workflow_repository.py     # Workflow definitions
│   ├── asset_repository.py        # Image/file assets
│   ├── sync_repository.py         # Connector sync logs/state
│   └── model_repository.py        # Managed LLM model registry
├── indexing/
│   ├── vector_index.py            # Qdrant indexing
│   └── keyword_index.py           # PostgreSQL fulltext indexing (GIN ts_vector)
├── permissions/
│   └── filter.py                  # PermissionFilter: filter docs theo user groups
├── storage/
│   ├── db/db.py                   # SQLAlchemy engine, session factory, create_tables
│   └── vector/vector_store.py     # Qdrant client wrapper
├── prompts/                       # Prompt templates
│   ├── agent_prompt.py            # PLAN_SYSTEM, SUMMARIZE_SYSTEM, SELF_CORRECT_SYSTEM...
│   ├── doc_draft_prompt.py        # Build prompts cho từng doc type
│   └── retrieval_prompt.py        # RERANK_SYSTEM
├── config/settings.py             # Pydantic Settings, đọc từ .env
├── scheduler/sync_scheduler.py    # APScheduler: auto-ingest scheduler
├── utils/                         # Logging, text, queue client, vision answer, embedding cache
├── models/                        # Pydantic models (Document, SearchQuery, SearchResult...)
├── docskill/
│   ├── mygpt-ba.skill             # SDLC 9-step skill definition (42KB)
│   ├── mygpt-ba/                  # Agents: gen_prompt.md, schema.json per step
│   └── SDLC_Prompt_Library_v1.md
├── knowledge_base/                # Tài liệu tiêu chuẩn nội bộ (BE, FE, QA, Ops)
├── web/                           # Frontend TypeScript SPA (Vite)
├── scripts/
│   ├── docx_bridge.js             # Node.js bridge for DOCX generation
│   ├── pptx_bridge.js             # Node.js bridge for PPTX generation
│   └── cron_worker.py             # Scheduled jobs runner
├── assets/
│   └── generated/                 # Tệp tin tạm được sinh ra từ workflow
├── run.py                         # Khởi động API (uvicorn)
├── run_worker.py                  # Khởi động arq worker
├── arq_worker.py                  # arq WorkerSettings + job registration
├── create_admin.py                # Script tạo admin user lần đầu
├── seed_workflow.py               # Script seed workflow mẫu
└── docker-compose.yml
```

---

## 4. Authentication & Authorization

### 4.1 Authentication

- JWT Bearer token, tự implement (không dùng thư viện OAuth/OIDC).
- Login: `POST /api/auth/login` → trả về JWT.
- JWT payload: `sub` (user_id), `email`, `is_admin`, `role`.
- `JWT_SECRET` = `"change-me-in-production"` (mặc định trong settings — phải đổi khi deploy).
- Token expire: 60 phút (`JWT_EXPIRE_MINUTES`), refresh token: 7 ngày.

### 4.2 Backend RBAC (thực tế enforce tại backend)

**`apps/api/auth/dependencies.py`** định nghĩa 3 dependency:

| Dependency | Điều kiện | Dùng cho |
|---|---|---|
| `get_current_user` | Chỉ cần JWT hợp lệ | Hầu hết routes |
| `require_admin` | `is_admin=True` | `/ingest`, sync Jira, admin-only ops |
| `require_task_manager` | role là `pm_po` hoặc `ba_sa` (hoặc admin) | Confirm/submit/scan task drafts |

**Role aliases** được normalize về canonical role:

| Input alias | Canonical role |
|---|---|
| `admin`, `sysadmin` | `system_admin` |
| `pm`, `po`, `team_lead`, `lead` | `pm_po` |
| `ba`, `sa`, `business_analyst` | `ba_sa` |
| `dev`, `developer`, `qa` | `dev_qa` |
| `member` | `standard` |
| `prompt_engineer` | `knowledge_architect` |

### 4.3 Frontend RBAC (bổ sung)

Ngoài backend, frontend cũng filter module hiển thị trong sidebar theo role (trong `web/main.ts`):

| Role | Modules được phép |
|---|---|
| `system_admin` / `is_admin` | Tất cả |
| `knowledge_architect` | chat, search, documents, graph, prompts, memory, models |
| `pm_po` | + tasks, drafts, ba-suite, workflows, dashboard |
| `ba_sa` | + tasks, drafts, ba-suite, workflows, dashboard |
| `dev_qa` | chat, search, documents, graph, tasks |
| `standard` | chat, search, documents, graph |

> [!TIP]
> **Project-Level Isolation**: PM Dashboard hiện đã áp dụng cơ chế lọc dữ liệu theo `project_key` gắn liền với `groups` của người dùng để đảm bảo tính riêng tư.

---

## 5. API Endpoints

Swagger: `/api/docs` | ReDoc: `/api/redoc`

| Prefix | Route file | Ghi chú |
|---|---|---|
| `/api/auth` | auth.py | Login, register, token refresh |
| `/api/ask` | ask.py | RAG Q&A (ReAct agent) |
| `/api/search` | search.py | Hybrid search, không qua LLM |
| `/api/ingest` | ingest.py | Trigger ingestion (require_admin) |
| `/api/connectors` | connectors.py | CRUD connector configs |
| `/api/graph` | graph.py | Entity/relation CRUD, graph query |
| `/api/docs` | docs.py | Draft CRUD, AI refine, memory |
| `/api/documents` | documents.py | Document management |
| `/api/users` | users.py | User CRUD |
| `/api/groups` | groups.py | Group management |
| `/api/prompts` | prompts.py | Skill prompt CRUD |
| `/api/tasks` | tasks/routes.py | AI Task Drafts (502 lines) |
| `/api/memory` | memory.py | Project memory store |
| `/api/history` | history.py | Chat history |
| `/api/workflows` | workflows.py | AI Workflow definitions |
| `/api/slack` | slack.py | Slack webhook |
| `/api/pm` | pm_routes.py | **PM Analytics & Dashboard (Hardened)** |
| `/api/models` | models.py | Managed LLM models registry |
| `/api/assets` | assets.py | File asset access |
| `/api/health` | health.py | Health check |
| `/api/sdlc/stream` | server.py (proxy) | SSE stream → rag_service:8001 |
| `/api/sdlc/generate` | server.py (proxy) | Sync generate → rag_service |
| `/api/sdlc/async` | server.py (proxy) | Enqueue SDLC job |
| `/api/sdlc/jobs/{id}` | server.py (proxy) | Poll SDLC job status |

---

## 6. RAG Pipeline (Chi tiết)

### 6.1 Luồng `/api/ask` (ReAct Agent)

```
User Question
    ↓
[1] Semantic Cache Lookup (Qdrant "semantic_cache", threshold 0.92)
    → HIT: trả về ngay (skip LLM)
    ↓ MISS
[2] Planner (LLM)
    → Câu ngắn (<40 chars, không có "và/and/so sánh"): fast path (1 plan step)
    → Câu dài: LLM tạo kế hoạch (tối đa 3 steps, có thể parallel)
    ↓
[3] Tool Execution (asyncio.gather cho parallel steps)
    → Mỗi step gọi RAGService.searchv2()
    ↓
[4] Self-Correction (nếu AGENT_SELF_CORRECT_ENABLED=True)
    → Grade top-4 sources bằng LLM (0-3 score)
    → Nếu best < 1.2 và avg < 1.1: rewrite query + retry search
    ↓
[5] Context Compression (retrieval/context_compressor.py)
    ↓
[6] LLM Summarize
    → Language detection (Vietnamese vs English qua regex ký tự dấu)
    → Answer ONLY from context
    ↓
[7] Logic Check (nếu AGENT_LOGIC_CHECK_ENABLED=True, len(sources)>=3)
    → Detect contradictions giữa các nguồn
    → Append confidence score vào answer
    ↓
[8] Semantic Cache Store (nếu answer không phải "Không tìm thấy...")
    ↓
Response: {answer, sources, agent_steps, plan, used_tools, rewritten_query}
```

### 6.2 RAGService.searchv2() — 8 bước trong một search call

```
[1] Permission Check
    → PermissionFilter.allowed_docs(user_id) → list[str] | None
    → None = không filter (toàn bộ), [] = không có quyền gì

[2] Query Expansion (nếu expand=True và QUERY_EXPANSION_ENABLED)
    → LLM tạo thêm query variants

[3] Parallel Hybrid Search
    → HybridSearch: vector search (Qdrant) + keyword search (BM25/PG)
    → Dedup by chunk_id

[4] Graph Augmentation (nếu GRAPH_AUGMENTATION_ENABLED)
    Hop 1: Lấy entities từ top-10 hits → find_related_entities (min_weight=2, limit=5/entity, max 15 entities)
    Hop 2: find_related_documents từ neighbor entities → supplement hits

[5] Metadata Enrichment
    → Fetch doc metadata từ PostgreSQL

[6] RankingScorer.score()
    → 5 signals: semantic × 0.5 + BM25 × 0.3 + graph × 0.2 + recency × 0.1 + popularity × 0.1
    → × source_weight (confluence=1.0, jira=0.9, file_server=0.8, slack=0.4)
    → × 1.8 nếu query xuất hiện trong title

[7] Reranking (nếu use_rerank=True và RERANKING_ENABLED)
    Stage 1: shortlist top max(limit×4, 25)
    Stage 2: Rerank bằng LLM hoặc Cross-Encoder
    → LLM mode: score 0-3, rerank_score = llm_score + 0.1×norm_orig
    → Cross-Encoder mode: ce_score + 0.01×norm_orig
    → Skip nếu rrf_score > 0.9 (already confident)
    → In-memory cache 120s, max 1000 entries

[8] Context Window + Assets
    → Load section context hoặc neighbor chunks
    → Fetch linked assets (images) theo chunk_id
    → Slack URL: build deep link từ timestamp

→ ContextBuilder.build(results)
    → Filter score < 0.4
    → Group by (document_id, section_title)
    → Dedup content trong nhóm
    → Token budget: max 2000 tokens/group (1 token ≈ 4 chars), truncate với "[TRUNCATED BY BUDGET]"
    → Sort group theo max score DESC

→ Return: {hits: grouped_results, relationships: graph_rel_strings}
```

---

## 7. Ingestion Pipeline (Chi tiết)

**`ingestion/pipeline.py`** — IngestionPipeline:

```
[1] Incremental Check
    → SyncRepository.get_last_sync(connector) → date | None
    → Nếu có: fetch_documents(last_sync=date) — chỉ lấy document mới

[2] Fetch Documents
    → connector.fetch_documents() → List[Document]
    → Progress log vào DB

[3] Batch Processing (batch_size=20, configurable)
    Mỗi document:
    a. TextCleaner.clean(content)       — loại bỏ noise
    b. AssetIngestor.enrich_document()  — download hình, OCR/caption nếu VISION_ENABLED
    c. MetadataExtractor.extract()      — title, author, dates...
    d. EntityExtractor.extract_typed()  — NER: person, tech, project, jira_key...
    e. IdentityResolver.resolve()       — merge người dùng qua aliases
    f. DocumentRepository.upsert()      — lưu vào PG
    g. KnowledgeGraph.link_document_entities() / link_document_identities()
    h. DocumentLinker.upsert_for_document() — cross-doc links
    i. Smart Chunking
       → Confluence: ConfluenceParser.parse_sections() → section-aware chunking
       → Khác: standard chunking (CHUNK_SIZE=500, OVERLAP=50)
    j. VectorIndex.index_chunks()       — embed + upsert vào Qdrant
    k. KeywordIndex.index_chunks()      — PostgreSQL fulltext index
    l. AssetRepository.link_chunk_assets() — link asset_id → chunk_id

[4] Progress Heartbeat
    → Update SyncRepository mỗi 3 docs hoặc 2 giây
    → Hỗ trợ cancellation: nếu `still_running=False`, dừng pipeline

[5] Finish Sync
    → status: "success" | "partial" | "failed" | "cancelled"
```

---

## 8. AI Task Drafts (Tasks Module)

Task module quản lý vòng đời của "AI-extracted task" từ Slack/Confluence đến Jira:

```
Scan (Slack/Confluence)
    ↓ scanner.py + task_writer.py
AI Extract (title, type, assignee, priority, labels)
    ↓
TaskDraft created in DB (status: "pending")
    ↓ Scope: scope_group_id (group-based access control)
PM/PO confirm/edit (status: "confirmed")
    ↓ require_task_manager
Submit to Jira (jira_creator.py)
    ↓
Status: "submitted", lưu jira_key
    ↓ scheduler: jira_sync.py
Sync Jira status về DB (manual: /tasks/sync-jira-status)
```

**Scope-based access:** Non-admin chỉ thấy drafts có `scope_group_id` trùng với group của họ.

---

## 9. Knowledge Graph (Chi tiết)

**Lưu trữ trong PostgreSQL** — 4 bảng:
- `entities`: id, name, normalized_name, entity_type
- `entity_aliases`: entity_id, normalized_alias, alias_value, alias_type, alias_strength
- `document_entities`: document_id, entity_id, entity_type
- `entity_relations`: source_id, target_id, relation_type (`co_occurs`), weight

**Entity types**: person, tech, project, jira_key, và các loại khác do EntityExtractor phát hiện.

**Identity Resolution**: người dùng có thể có nhiều aliases (email, Slack handle, Jira account_id). `IdentityResolver` merge chúng dựa trên điểm số (strong_alias=100pts, medium_alias=40pts, name_match=10pts).

**2-hop traversal** trong `searchv2()`:
- Hop 1: từ entities của top-10 docs → `find_related_entities(min_weight=2)` → neighbor entities
- Hop 2: `find_related_documents(neighbor_entities)` → bổ sung docs vào search results với `graph_score=1.0`

---

## 10. Background Job System (arq)

**3 queue riêng biệt:**

| Queue | Worker | Jobs | Timeout |
|---|---|---|---|
| `arq:default` | worker_default | Misc tasks | 120s |
| `arq:ingestion` | worker_ingestion | Connector sync jobs | 21600s (6h) |
| `arq:ai` | worker_ai | Document drafting, AI Workflows (Export/Notify) | 1500s (25min) |

**AI Workflow & Automation Flow (async)**:
1. API tạo "stub" job (status=`processing`)
2. Enqueue `run_workflow_job` vào `arq:ai`
3. `worker_ai` pick up → Duyệt từng Node trong Workflow
    * **Export Node**: Gọi subprocess `node scripts/xxx_bridge.js`
    * **Notification Node**: Gọi Slack API hoặc `send_email_async` (tự động đính kèm file)
4. Update result trả về Markdown chuỗi kết quả hoặc Link download
5. Frontend polling hiển thị tiến độ và nút **Premium Preview**

---

## 11. Cấu hình môi trường (`.env`)

Các biến quan trọng:

```env
# Database (PostgreSQL local, không trong Docker)
DATABASE_URL=postgresql+asyncpg://postgres:pass@localhost:5432/knowledge_platform
DATABASE_SYNC_URL=postgresql://postgres:pass@localhost:5432/knowledge_platform
DATABASE_POOL_SIZE=30         # Optimized cho 30 concurrent users
DATABASE_MAX_OVERFLOW=10

# Infrastructure
REDIS_URL=redis://localhost:6379/0
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_COLLECTION=knowledge_chunks

# LLM (Ollama local hoặc bất kỳ OpenAI-compatible)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=qwen2.5:14b
OLLAMA_EMBED_MODEL=bge-m3
LLM_PROVIDER=ollama           # ollama | vllm | openai
INFERENCE_BASE_URL=           # Cho vLLM/OpenAI compatible
VECTOR_DIM=1024               # Phải khớp với embedding model
LLM_TIMEOUT=900               # 15 phút
ARQ_AI_JOB_TIMEOUT=1500      # 25 phút

# RAG Tuning
HYBRID_ALPHA=0.5              # Trọng số semantic
BM25_WEIGHT=0.3
GRAPH_WEIGHT=0.2
RECENCY_WEIGHT=0.1
POPULARITY_WEIGHT=0.1
TOP_K=10
CHUNK_SIZE=500
CHUNK_OVERLAP=50
RERANKER_BACKEND=llm          # llm | cross_encoder | none
CROSS_ENCODER_MODEL=BAAI/bge-reranker-base
SEMANTIC_CACHE_ENABLED=True
SEMANTIC_CACHE_THRESHOLD=0.92
QUERY_EXPANSION_ENABLED=True
GRAPH_AUGMENTATION_ENABLED=True

# Agent
AGENT_MAX_STEPS=5
AGENT_REACT_TIMEOUT=900
AGENT_MAX_PLAN_STEPS=3
AGENT_SELF_CORRECT_ENABLED=True
AGENT_LOGIC_CHECK_ENABLED=True

# Auth
JWT_SECRET=change-me-in-production   # BẮT BUỘC đổi trước khi deploy
JWT_EXPIRE_MINUTES=60

# Vision (OCR/Caption)
VISION_ENABLED=True           # Enable nếu có GPU mạnh và vision model
OLLAMA_VISION_MODEL=llava-phi3
VISION_MAX_IMAGES_PER_DOC=8

# Worker
RUN_WORKER=False              # True để chạy worker cùng API process
ARQ_WORKER_TYPE=ai            # ai | default | ingestion
ARQ_INGESTION_MAX_JOBS=2      # Giới hạn job cho ingestion để tránh quá tải
ARQ_DEFAULT_MAX_JOBS=10

# Connectors (tùy chọn)
JIRA_URL=
JIRA_USERNAME=
JIRA_API_TOKEN=
CONFLUENCE_URL=
CONFLUENCE_API_TOKEN=
SLACK_BOT_TOKEN=
SMB_HOST=
ZOOM_ACCOUNT_ID=              # JWT/Server-to-Server Auth
GOOGLE_DRIVE_FOLDER_ID=       # Google Service Account JSON required in config/
```

---

## 12. Hạn chế kỹ thuật đã biết

| # | Vấn đề | Mức độ | Trạng thái |
|---|---|---|---|
| 1 | `JWT_SECRET` mặc định — phải đổi khi deploy | **Nghiêm trọng** | Warning |
| 2 | CORS `allow_origins=["*"]` — không phù hợp production | **Cao** | Warning |
| 3 | PostgreSQL không có trong docker-compose — phải cài riêng | Trung bình | - |
| 4 | Không có test suite (unit/integration) toàn diện | **Cao** | Đang bổ sung |
| 5 | SDLC step cards dùng time-based simulation đơn giản | Thấp | - |
| 6 | Ollama chưa có cloud fallback | Trung bình | - |
| 7 | Reranker cache là in-memory dict | Thấp | - |
| 8 | Vision mặc định cần bật thủ công | Thấp | Cải thiện: `VISION_ENABLED=True` |
| 9 | `AGENT_LOGIC_CHECK_ENABLED` tăng độ trễ đáng kể | Trung bình | Cần tối ưu |
| 10 | Security: Dashboard đã được hardening project-level | - | **Đã hoàn thành (v2.1)** |

---

## 13. Khởi chạy (Development)

**Điều kiện tiên quyết:**
- Python 3.11+, Node.js 18+, Docker Desktop
- PostgreSQL cài và chạy local (port 5432)
- Ollama cài và chạy với model cần thiết:
  ```bash
  ollama pull qwen2.5:14b
  ollama pull bge-m3
  # (Optional) ollama pull llava-phi3  # nếu dùng vision
  ```

```bash
# 1. Infrastructure (Redis + Qdrant)
docker compose up -d redis qdrant

# 2. Python setup
python -m venv venv
venv\Scripts\activate       # Windows
pip install -r requirements.txt

# 3. Tạo DB tables (Alembic hoặc auto-create)
# Auto-create khi chạy lần đầu (lifespan startup)

# 4. Tạo admin user
python create_admin.py

# 5. API
python run.py               # Port 8000

# 6. Workers (mỗi cái 1 terminal)
set ARQ_WORKER_TYPE=ai && python run_worker.py
set ARQ_WORKER_TYPE=default && python run_worker.py
set ARQ_WORKER_TYPE=ingestion && python run_worker.py

# 7. Frontend (dev)
cd web
npm install
npm run dev                 # Vite dev server

# 8. Frontend (production build)
npm run build               # Output → web/dist/
```
