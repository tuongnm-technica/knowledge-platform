# Knowledge Platform — Step-by-Step SDLC Suite v4

Hệ thống quản trị tri thức và tự động hóa quy trình phần mềm (SDLC) dựa trên Multi-Agent Orchestration. Dự án đã được chuẩn hóa sang mô hình **Production-Ready** với quy trình 9 bước (Step 1-9) và kiến trúc tách lớp tri thức.

---

## 🚀 Key Features

- **9-Step SDLC Pipeline**: Quy trình tự động từ lấy yêu cầu (Intake) đến quản lý phát hành (Release).
- **Async Task Management**: Hệ thống quản lý tác vụ ngầm (Background Jobs) hỗ trợ xử lý song song các tài liệu BA cồng kềnh, có khả năng theo dõi trạng thái và lịch sử (Persistence).
- **Intelligent Task Orchestration (Auto-Quest)**: Tự động khởi tạo các tác vụ soạn thảo (Drafts) dựa trên kết quả phân tích yêu cầu, giúp liền mạch từ ý tưởng đến tài liệu kỹ thuật.
- **Tri-Layer Skill Architecture**: Tách biệt hoàn toàn Prompt (Instruction), Schema (Validation), và Template (Rendering) để tối ưu hóa context window.
- **Expert Knowledge Hardened**: Tích hợp các tiêu chuẩn chuyên gia (BA, SA, QA, DevOps) dưới dạng "Execution Specs" (DoD, Runtime Behavior, Quality Gates).
- **Smart Dynamic Truncation**: Tự động cân đối dung lượng tài liệu đầu vào để đảm bảo không tràn bộ nhớ ngữ cảnh LLM.
- **Multi-Source Ingestion**: Hỗ trợ Jira, Confluence, Slack, và File Server với khả năng xử lý Multiple Vision (OCR/Captioning).

---

## 🏗️ Architecture Overview

Hệ thống vận hành dựa trên 5 Pipeline cốt lõi:
1.  **SDLC Agentic Pipeline**: Điều phối Step 1-9.
2.  **Document Ingestion**: Thu thập và làm sạch dữ liệu.
3.  **Knowledge Retrieval (RAG)**: Tìm kiếm ngữ cảnh dựa trên Vector & Keyword.
4.  **Background Worker**: Xử lý các tác vụ nặng (Drafting, Ingest) không chặn API.
5.  **Task Lifecycle**: Quản lý trạng thái và lịch sử công việc.

---

## 📋 SDLC Pipeline Steps (Step 1-9)

| Step | Unit Name | Outputs |
|------|-----------|---------|
| **Step 1** | Requirement Analyst | FR, NFR, BR, Assumptions, Intake JSON |
| **Step 2** | Architect Reviewer | Logic Review, Permission Model, Edge Cases |
| **Step 3** | Solution Designer | Architecture, ADR, API Contract, Data Model |
| **Step 4** | Document Writer | SRS, BRD, Use Cases, Validation Rules |
| **Step 5** | User Story Writer | User Stories, Gherkin AC, INVEST, DoD |
| **Step 6** | FE Technical Spec | Component Tree, UI State, a11y, Perf Budget |
| **Step 7** | QA Reviewer | Test Cases (5 levels), OWASP, UAT Matrix |
| **Step 8** | Deployment Spec | CI/CD, Monitoring, Runbook, DR Plan |
| **Step 9** | Change & Release Mgr | CR, Impact Analysis, Release Notes, Risk Log |

---

## 📂 Project Structure (Comprehensive)

```text
.
├── apps/api/              # Tầng application (FastAPI server, routes, middleware)
│   └── routes/            # Các endpoint: /ask (RAG), /ingest (Data), /docs (Drafting)
├── orchestration/         # Điều phối toàn bộ pipeline AI (Agent, Tooling)
├── prompts/               # Centralized Prompt Engine (Doc Draft, Answer, Rewrite)
├── docskill/mygpt-ba/     # Step-by-Step Skill Suite (Môi trường tri thức cho BA)
│   └── agents/            # Tri-Layer: gen_prompt.md, schema.json, human_template.md
├── knowledge_base/        # Warehouse tri thức thực chiến (Standards cho BE, FE, QA, Ops)
├── ingestion/             # Pipeline xử lý dữ liệu (Cleaner, Chunker, Metadata Extractor)
├── connectors/            # Kết nối các nguồn dữ liệu (Jira, Confluence, Slack, Files)
├── retrieval/             # Chiến lược tìm kiếm (Vector, Keyword, Hybrid)
├── ranking/               # Chấm điểm và sắp xếp kết quả (Scorer, Signal scoring)
├── indexing/              # Tạo Index cho dữ liệu (Vector Index, Keyword Index)
├── persistence/           # DB Repositories (Document, Summary, Job status)
├── permissions/           # Kiểm soát quyền truy cập (ACL, Permission Filters)
├── query/                 # Phân tích câu hỏi (Parser, Intent Detector)
├── graph/                 # Knowledge Graph layer (Entity Extraction, Relationships)
├── tasks/                 # Background Jobs (Xử lý drafting Step 1-9 dài hơi)
├── storage/               # Tầng Database & Vector Store connectors
├── services/              # Các service dùng chung (LLM, Embeddings, Storage)
├── config/                # Cấu hình môi trường & Settings
├── legacy/                # Lưu trữ các file script & test cũ (Archived)
├── utils/                 # Các hàm phụ trợ (Logging, Text processing)
├── assets/                # Lưu trữ hình ảnh & tệp tin đa phương tiện
├── web/                   # Frontend assets / Static files (nếu có)
├── arq_worker.py          # Entry point cho Async Worker
├── run.py                 # Entry point khởi động API
└── docker-compose.yml     # Orchestration cho hạ tầng (Redis, PG, Qdrant, Ollama)
```

---

## 🛠️ Setup & Operation

### 1. Khởi chạy Infrastructure:
```bash
docker compose up -d
```

### 2. Chạy API & Worker cục bộ:
```bash
python run.py          # API (Port 8000)
python run_worker.py   # Async Worker
```

### 3. Cập nhật hệ thống:
Mỗi khi thay đổi `prompts/` hoặc `knowledge_base/`, hãy thực hiện:
```bash
docker compose restart api worker_ai worker_default
```

---

## 🖼️ Vision & Multi-Modal Support
Hệ thống hỗ trợ Vision qua Ollama (e.g., `llava:13b`). Ảnh từ tài liệu sẽ được OCR/Captioning tự động để phục vụ tìm kiếm ngữ cảnh.
- `ASSETS_DIR=assets`
- `VISION_ENABLED=true`
