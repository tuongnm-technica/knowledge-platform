# TÀI LIỆU THIẾT KẾ KỸ THUẬT TOÀN DIỆN

**Hệ thống:** KNOWLEDGE PLATFORM & MYGPT SDLC SUITE  
**Đối tượng sử dụng:** Dev Lead, Solution Architect, DevOps, Kỹ sư AI  
**Phiên bản:** 2.0 (Kiến trúc Graph & Multi-Agent)  

---

## 1. TỔNG QUAN HỆ THỐNG (SYSTEM OVERVIEW)
**Knowledge Platform** là một nền tảng "Đồng nghiệp AI cấp doanh nghiệp", kết hợp công nghệ RAG (Retrieval-Augmented Generation), **Knowledge Graph** (Lưới tri thức) và kiến trúc **Multi-Agent Pipeline**.

Hệ thống đóng vai trò như một dây chuyền tự động hóa: Nhận đầu vào thô (meeting notes, tin nhắn Slack, tài liệu Confluence), tự động học hỏi ngữ cảnh, và chạy qua chuỗi 9 tác tử AI để xuất ra các bộ tài liệu (SRS, BRD, Use Cases) chuẩn định dạng. Điểm cuối của hệ thống là **Task Engine** tự động phân rã nghiệp vụ và đẩy trực tiếp thành ticket trên hệ thống quản lý dự án (Jira).

---

## 2. KIẾN TRÚC CỐT LÕI (CORE ARCHITECTURE)

### 2.1. Kiến trúc 4 Lớp của AI Agents (4-Layer Structured Output)
Đây là pattern thiết kế bắt buộc cho toàn bộ pipeline để chống AI "ảo giác" (hallucinate):
1. **Layer 1 (Prompt):** System instruction chỉ định vai trò cho LLM. Nhúng trực tiếp cấu trúc JSON rỗng vào prompt.
2. **Layer 2 (Machine Template):** Khuôn mẫu JSON (JSON skeleton) trống làm ground truth. Các trường dữ liệu bắt buộc phải có.
3. **Layer 3 (JSON Schema):** Bộ quy tắc validate output (Sử dụng `jsonschema` với thuộc tính `additionalProperties: false`). Nếu validate fail, hệ thống sẽ chặn không cho luồng đi tiếp hoặc tự động retry.
4. **Layer 4 (Human Template):** Hệ thống Template (Markdown/UI) render dữ liệu JSON thành văn bản cho con người duyệt.

### 2.2. Kiến trúc CSDL Hybrid (Hybrid Database Architecture)
Hệ thống sử dụng đồng thời 3 loại cơ sở dữ liệu:
*   **Relational DB (PostgreSQL):** Quản lý định danh User, Phân quyền (RBAC), và lưu trữ trạng thái Pipeline (bản nháp).
*   **Vector DB (Qdrant):** Lưu trữ Embeddings của tài liệu (Chunks), xử lý Semantic Search.
*   **Graph DB:** Trích xuất và lưu trữ thực thể (Entity) cùng các mối quan hệ (Relationships) để giải quyết các truy vấn tổng hợp phức tạp (GraphRAG).

---

## 3. SƠ ĐỒ LUỒNG VÀ TRẠNG THÁI (PIPELINE FLOWCHART)
Hệ thống hoạt động bất đồng bộ, sử dụng cơ chế **State Machine** để quản lý trạng thái luân chuyển dữ liệu.

### 3.1. Chốt chặn phê duyệt (Human-in-the-loop)
Hệ thống không chạy thác đổ một chiều. Sau mỗi Agent quan trọng, dữ liệu nháp được lưu xuống Database ở trạng thái `PENDING_REVIEW`. Người dùng (BA/SA) lên giao diện kiểm tra, chỉnh sửa, ấn `Approve` thì Agent tiếp theo mới được kích hoạt.

### 3.2. Vòng lặp phản hồi (Reject Routing)
Các tác tử đóng vai trò Reviewer (`GPT-2`, `GPT-7`) có khả năng tự suy luận logic. Nếu phát hiện đầu vào bị thiếu, sai hoặc mâu thuẫn, chúng xuất ra schema `{"status": "reject"}`. Hệ thống sẽ bắt cờ này và đẩy state ngược lại bước trước (Feedback Loop) để yêu cầu Agent trước xử lý lại hoặc thông báo cho người dùng bổ sung.

---

## 4. CẤU TRÚC REPOSITORY (DIRECTORY TREE)

```text
knowledge-platform/
├── config/
│   └── settings.py                 # Biến môi trường, config
├── docskill/                       # Bộ não của Multi-Agent
│   ├── mygpt-ba/                   # Orchestrator & Router cho 9 Agents
│   │   ├── SKILL.md                # Flow chính & Reject routing
│   │   ├── Pipeline_Flowchart.md   # Mô tả luồng (Mermaid Diagram)
│   │   └── references/             # Chứa 9 file .md của 9 GPTs (Kèm JSON Schema)
│   └── SDLC_Prompt_Library_v1.md   # Thư viện 17 prompt patterns rời
├── prompts/                        # System Prompts hỗ trợ
│   ├── rewrite_prompt.py           # Tiền xử lý câu hỏi RAG
│   └── summary_prompt.py           # Trích xuất thông tin trọng tâm (Distill)
├── retrieval/                      # Search & Reranking Engine
│   └── reranker.py                 # Thuật toán rerank (Cross-encoder & LLM fallback)
├── tasks/                          # Business logic cho background jobs
│   └── scanner.py                  # Thu thập dữ liệu Slack/Confluence
├── scripts/                        # Kịch bản CI/CD, vận hành
│   ├── fresh_reset.py              # Dọn dẹp DB & File, khởi tạo từ đầu
│   └── reset_db.py                 # Dọn dẹp DB & tạo Admin gốc
└── arq_worker.py                   # Worker Async chạy ngầm (Ingestion & AI Tasks)
```

---

## 5. THIẾT KẾ CÁC PHÂN HỆ CHI TIẾT (MODULE SPECIFICATIONS)

### 5.1. Phân hệ Data Ingestion & Knowledge Graph
Sử dụng hàng đợi **Redis + Arq Worker** (`arq_worker.py`) để chạy các tác vụ cào dữ liệu ngầm cực nặng mà không làm đứng API Server.
*   **Slack/Confluence Scanner:** Kết nối API quét nội dung, lọc thread nhóm theo context, bóc tách HTML sang Markdown.
*   **Graph Extractor:** Phân tích tài liệu tìm được, móc nối các thực thể (Entity Linking) để vẽ lên đồ thị tri thức nội bộ.

### 5.2. Phân hệ MyGPT BA Suite (Pipeline 9 Agents)
Luồng luân chuyển truyền ID liên tục (`intake_id` ➔ `design_ref` ➔ `doc_ref`):
*   **[GPT-1]** Bóc tách Requirement (FR/NFR/BR).
*   **[GPT-2 & 3]** Review Logic, thiết kế Architecture, sinh API Contract (RFC 7807).
*   **[GPT-4]** Render tài liệu chuẩn: SRS (10 mục), BRD, Use Cases.
*   **[GPT-6 & 7]** Thiết kế Component UI Spec & Viết Test cases chuẩn ISTQB.
*   **[GPT-8 & 9]** Viết Runbook, Phân tích ảnh hưởng (Impact Analysis) CR và sinh Release Notes.

### 5.3. Phân hệ Task Engine (Tích hợp Jira)
Tác tử **[GPT-5] User Story Writer** làm nhiệm vụ đọc Use Case, phân rã thành thẻ Agile (Epic -> Story -> Sub-tasks) với Acceptance Criteria viết bằng Gherkin. 
*   JSON Schema (Layer 3) của tác tử này được map 1-1 với Payload của **Jira REST API v3**. 
*   Hệ thống Backend (Python `atlassian-python-api`) consume JSON này để đẩy hàng loạt task lên Backlog.

### 5.4. Phân hệ RAG & Reranker Engine
*   **Query Rewrite:** Dùng LLM làm sạch câu truy vấn của user, loại bỏ từ thừa (`rewrite_prompt.py`).
*   **Reranker (`reranker.py`):** Module cốt lõi. Ưu tiên chấm điểm lại top kết quả search bằng thuật toán Cross-encoder cục bộ (`sentence_transformers`). 
*   **LLM Fallback:** Lùi về dùng LLM scoring nếu model ML lỗi.
*   **Cache Tối ưu:** Bảo vệ server bằng cache giới hạn (`_MAX_CACHE_SIZE = 1000`) và TTL 120s chống query trùng lặp.

---

## 6. BẢO MẬT & QUẢN TRỊ VẬN HÀNH (SECURITY & OPERATIONS)

### 6.1. Định danh và Phân quyền (IAM)
Sử dụng `bcrypt` (gen salt) mã hóa pass xuống Postgres. Hệ thống áp dụng **RBAC (Role-based Access Control)**, phân quyền đọc/ghi RAG dựa trên cấp độ bảo mật tài liệu và Group của User.

### 6.2. Kịch bản Reset Hệ thống
Cung cấp script setup phục vụ môi trường Dev/Staging:
*   `reset_db.py`: Truncate CSDL PostgreSQL và xóa cấu trúc Qdrant Vector.
*   `fresh_reset.py`: Deep clean CSDL, dọn rác tệp vật lý (`ASSETS_DIR`), tái tạo Admin Account qua biến môi trường (`os.getenv`), và mồi (seed) lại toàn bộ kho Prompts gốc.

---

## 7. BẢNG CÔNG NGHỆ BỘ KHUNG (TECH STACK)

| Lớp (Layer) | Công nghệ / Thư viện | Mục đích sử dụng |
| :--- | :--- | :--- |
| **Ngôn ngữ lõi** | **Python 3.10+** (Asyncio) | Backend bất đồng bộ (FastAPI), không block khi chờ LLM/DB. |
| **DB Quan hệ** | **PostgreSQL (asyncpg)** | Lưu User, RBAC, Trạng thái Pipeline, Logs. |
| **Vector DB** | **Qdrant** | Lưu Embeddings (chunk_ids) phục vụ Semantic Search nhanh. |
| **ORM** | **SQLAlchemy** | Thao tác DB an toàn, quản lý migration. |
| **Job Queue** | **Redis + arq** | Chạy Ingestion Workers (Slack, Confluence) ở background. |
| **AI / Graph** | **langgraph, langchain** | Quản lý luồng Agent (State machine) và Text splitting. |
| **NLP Engine** | **sentence-transformers** | Chạy mô hình Cross-Encoder tại CPU/GPU nội bộ để Rerank. |
| **API Client** | **httpx / slack_sdk / atlassian** | Giao tiếp với External APIs (LLMs, Slack, Jira). |
| **Validation** | **jsonschema** | Ràng buộc Schema JSON (Layer 3), triệt tiêu Hallucination. |

---

## 8. CHI TIẾT CHỨC NĂNG CÁC TỆP TIN CHÍNH (FILE DETAILS)

*   **`arq_worker.py`:** Chứa định nghĩa các Queue (nhẹ, nặng, AI). Xử lý các task cào dữ liệu (`scan_sources_job`) tránh làm nghẽn Main Server.
*   **`reranker.py`:** Chứa thuật toán chấm điểm và sắp xếp kết quả. Tích hợp lock Async (`_cross_encoder_lock`) để không sập GPU khi load nhiều mô hình cùng lúc.
*   **`SKILL.md`:** Khai báo Workflow Orchestrator, bảng định tuyến (routing) xử lý câu hỏi của user để điều hướng vào đúng Agent.
*   **`gpt5-user-story-writer.md`:** Trí tuệ của tác tử GPT-5, sinh JSON Payload chuẩn cho Jira.

---

## 9. DANH MỤC CHỨC NĂNG CỐT LÕI (FUNCTION LIST)

| Phân hệ | ID | Tên chức năng | Mô tả chức năng |
| :--- | :--- | :--- | :--- |
| **Ingestion** | ING-01 | Tích hợp Confluence & Slack | Worker cào dữ liệu ngầm, phân tích Thread và bóc tách HTML sang Markdown. |
| **Graph DB**| GPH-01 | Trích xuất Thực thể | AI đọc tài liệu thu về, liên kết các thuật ngữ (Entities) để xây đồ thị. |
| **RAG Engine** | RET-01 | Tối ưu truy vấn & Rerank | Tiền xử lý query, chấm điểm bằng Cross-encoder kết hợp bộ Cache chống tràn. |
| **Multi-Agent** | AGT-01 | Lớp Xác thực Cấu trúc | Ép 100% output qua Lớp 3 (JSON Schema). Tự động chặn/thử lại với dữ liệu rác. |
| | AGT-02 | Pipeline Reject Routing | Cho phép Agent bắt lỗi mâu thuẫn logic và đẩy trạng thái lùi lại (Feedback loop). |
| | AGT-03 | Phân rã Document | Sinh tài liệu end-to-end từ Requirement, Architecture Design đến Test Cases, Release Notes. |
| **Task Engine** | TSK-01 | Tự tạo Ticket Jira | Rã Use Case thành Epic/Story/Sub-task và đẩy lên Jira via REST API. |
| **System** | SYS-01 | Database Fresh Reset | Truncate toàn diện Postgres, Qdrant và dọn rác tệp vật lý bằng script tự động. |

---
*(Tài liệu này bao quát toàn bộ thiết kế kiến trúc AI, Data Pipeline, và các tiêu chuẩn kiểm soát chất lượng tích hợp cho dự án)*