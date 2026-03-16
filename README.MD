knowledge-platform
│
├ apps                              -- Tầng application (API layer, nơi client gọi vào hệ thống)
│   └ api
│       ├ server.py                 -- Khởi tạo FastAPI server, register routes, middleware, startup/shutdown, health check
│       └ routes
│           ├ ask.py                -- API hỏi AI (RAG pipeline: query → retrieval → ranking → permission → LLM)
│           ├ search.py             -- API search tài liệu (chỉ retrieval + ranking, không gọi LLM)
│           └ ingest.py             -- API ingest dữ liệu (trigger connectors → ingestion → indexing)
│
├ config                            -- Cấu hình hệ thống
│   └ settings.py                   -- Biến môi trường: DB URL, vector DB, API keys, model config
│
├ connectors                        -- Kết nối các nguồn dữ liệu bên ngoài (data sources)
│   ├ base
│   │   └ base_connector.py         -- Interface chuẩn cho mọi connector (fetch, parse, permission)
│   │
│   ├ slack
│   │   ├ slack_connector.py        -- Orchestrator lấy dữ liệu Slack (channels, threads)
│   │   ├ slack_client.py           -- Client gọi Slack API
│   │   ├ slack_parser.py           -- Parse message Slack → document format
│   │   └ slack_permissions.py      -- Xác định quyền truy cập Slack message
│   │
│   ├ confluence
│   │   ├ confluence_connector.py   -- Lấy page và content từ Confluence
│   │   ├ confluence_client.py      -- Client gọi Confluence API
│   │   ├ confluence_parser.py      -- Parse wiki page → text
│   │   └ confluence_permissions.py -- Mapping quyền truy cập Confluence
│   │
│   └ jira
│       ├ jira_connector.py         -- Lấy issue/ticket từ Jira
│       ├ jira_client.py            -- Client gọi Jira REST API
│       └ jira_parser.py            -- Parse issue → document
│
├ ingestion                         -- Pipeline xử lý dữ liệu trước khi index
│   ├ pipeline.py                   -- Điều phối ingestion: clean → chunk → metadata → index
│   ├ cleaner.py                    -- Làm sạch text (remove HTML, markdown, noise)
│   ├ chunker.py                    -- Chia document thành chunks cho embedding
│   └ metadata_extractor.py         -- Trích metadata (author, timestamp, source, permissions)
│
├ indexing                          -- Tạo index để tìm kiếm
│   ├ vector_index.py               -- Tạo embedding và lưu vào vector database
│   └ keyword_index.py              -- Tạo inverted index cho keyword search
│
├ retrieval                         -- Các chiến lược tìm kiếm
│   ├ vector
│   │   └ vector_search.py          -- Semantic search bằng vector similarity
│   │
│   ├ keyword
│   │   └ keyword_search.py         -- Search theo keyword (BM25 hoặc TF-IDF)
│   │
│   └ hybrid
│       └ hybrid_search.py          -- Kết hợp vector search + keyword search
│
├ ranking                           -- Chấm điểm và sắp xếp kết quả search
│   ├ scorer.py                     -- Tính điểm relevance của documents
│   └ signals.py                    -- Các tín hiệu ranking (recency, source quality, popularity)
│
├ permissions                       -- Kiểm soát quyền truy cập tài liệu
│   ├ acl.py                        -- Access Control List (mapping user ↔ document permissions)
│   └ filter.py                     -- Lọc documents theo quyền trước khi trả về
│
├ prompts                           -- Prompt templates cho LLM
│   ├ answer_prompt.py              -- Prompt tạo câu trả lời từ context
│   ├ rewrite_prompt.py             -- Prompt rewrite query để search tốt hơn
│   └ summary_prompt.py             -- Prompt tóm tắt tài liệu
│
├ query                             -- Phân tích câu hỏi của user
│   ├ query_parser.py               -- Parse query thành structure (entities, keywords)
│   └ intent_detector.py            -- Xác định intent (search, QA, summary, etc.)
│
├ graph                             -- Knowledge graph layer
│   ├ entity_extractor.py           -- Trích entity từ document
│   └ knowledge_graph.py            -- Lưu và truy vấn graph relationships
│
├ orchestration                     -- Điều phối toàn bộ pipeline AI
│   └ agent.py                      -- Agent điều khiển flow: query → retrieval → ranking → permission → LLM
│
├ persistence                       -- Lưu dữ liệu ứng dụng
│   ├ document_repository.py        -- CRUD documents trong database
│   └ summary_repository.py         -- Lưu summary và cache kết quả
│
├ storage                           -- Tầng lưu trữ
│   ├ db
│   │   └ db.py                     -- Kết nối database (Postgres/MySQL)
│   │
│   └ vector
│       └ vector_store.py           -- Kết nối vector database (Qdrant/Pinecone/Weaviate)
│
├ models                            -- Data models (schema)
│   ├ document.py                   -- Schema document (id, text, metadata)
│   ├ query.py                      -- Schema query request
│   └ user.py                       -- Schema user và roles
│
├ utils                             -- Utility functions dùng chung
│   ├ logging.py                    -- Setup logging toàn hệ thống
│   └ text_utils.py                 -- Các hàm xử lý text
│
├ tests                             -- Unit tests và integration tests
│
├ run.py                            -- Entry point chạy server (uvicorn)
├ requirements.txt                  -- Danh sách dependencies Python
└ README.md                         -- Tài liệu mô tả project

---

## Vision / Image Context (Multiple Vision)

Hệ thống hỗ trợ ingest ảnh (diagram/screenshot/chart/whiteboard) từ Confluence/Jira/Slack/File Server:

- Connectors chèn placeholder `[[IMAGE:...]]`, `[[SLACK_FILE:...]]`, `[[JIRA_ATTACHMENT:...]]`, `[[IMPORTED_ASSET:...]]` vào text.
- Ingestion sẽ tải ảnh về `ASSETS_DIR`, lưu metadata vào DB (`document_assets`, `chunk_assets`), (tuỳ chọn) chạy caption/OCR bằng Ollama vision model và chèn lại caption vào content để embedding/search match được.
- Q&A có thể gửi kèm 1-2 ảnh liên quan nhất cho vision model (nếu bật).

Biến môi trường chính (xem `config/settings.py`):

- `ASSETS_DIR=assets`
- `VISION_ENABLED=true`
- `OLLAMA_VISION_MODEL=llava:13b` (cần model vision được cài trong Ollama)
