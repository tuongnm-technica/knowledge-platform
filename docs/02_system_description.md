# Tài liệu Mô tả Hệ thống — Knowledge Platform

> **Phiên bản:** 2.0 | **Ngày:** 2026-03-30  
> **Đối tượng:** PM, BA, SA, Team Lead — hiểu hệ thống làm gì, không cần đọc code

---

## 1. Hệ thống này là gì?

Knowledge Platform là **công cụ nội bộ đang được phát triển**, phục vụ hai mục tiêu:

**Mục tiêu 1:** Tìm kiếm thông minh trong tài liệu nội bộ — hỏi câu hỏi bằng tiếng tự nhiên, nhận câu trả lời tổng hợp từ tài liệu thực tế.

**Mục tiêu 2:** Hỗ trợ soạn thảo tài liệu SDLC — tự động tạo bản nháp SRS, BRD, Test Plan... và phối hợp chuỗi 9 AI agent để phân tích yêu cầu nghiệp vụ.

**Trạng thái:** Internal tool, đang phát triển. Chưa phải sản phẩm production hoàn chỉnh.

---

## 2. Kiến trúc tổng thể

```
┌─────────────────────────────────────────────────────────┐
│              NGƯỜI DÙNG (Browser)                        │
│         TypeScript SPA — Navigo routing, RBAC           │
└────────────────────────┬────────────────────────────────┘
                         │ REST / SSE
                         ▼
┌─────────────────────────────────────────────────────────┐
│        API Server — FastAPI (port 8000)                  │
│  /api/auth  /api/ask  /api/search  /api/docs  /api/tasks│
│  /api/graph  /api/connectors  /api/users  ...           │
│                                                         │
│  Proxy: /api/sdlc/* ──────────────────────────────────┐ │
└──────┬─────────────────┬────────── ┬───────────────────┼─┘
       │                 │           │                   │
       ▼                 ▼           ▼                   ▼
┌──────────┐  ┌──────────────┐ ┌──────────┐  ┌─────────────────┐
│PostgreSQL│  │Qdrant Vector │ │Redis arq │  │rag_service:8001 │
│(local)   │  │DB (Docker)   │ │(Docker)  │  │SDLC Orchestration│
└──────────┘  └──────────────┘ └────┬─────┘  └─────────────────┘
                                    │
                 ┌──────────────────┴──────────────────┐
                 │           arq Workers                │
                 ├────────────┬─────────┬──────────────┤
                 │worker_ai   │worker_  │worker_       │
                 │(Drafting)  │default  │ingestion     │
                 └─────┬──────┴─────────┴──────────────┘
                       │
                       ▼
                ┌─────────────┐
                │Ollama (local│
                │LLM + Embed) │
                └─────────────┘
```

---

## 3. Các module chức năng

### 3.1 Chat AI — Hỏi đáp thông minh

Người dùng đặt câu hỏi bằng ngôn ngữ tự nhiên. Hệ thống chạy **ReAct Agent** với các bước:

1. **Kiểm tra Semantic Cache** — câu hỏi tương tự đã được trả lời trước đó không? (nếu có, trả về ngay)
2. **Lập kế hoạch** — LLM phân tích câu hỏi, chia thành 1-3 sub-queries song song
3. **Tìm kiếm hybrid** — kết hợp vector search (ngữ nghĩa) + keyword search (BM25)
4. **Graph Augmentation** — mở rộng kết quả thông qua đồ thị tri thức (2 bậc)
5. **Reranking** — chấm điểm lại bằng LLM hoặc Cross-Encoder
6. **Tự sửa lỗi** — nếu kết quả yếu, rewrite query và tìm lại
7. **Tổng hợp câu trả lời** — LLM trả lời dựa trên context, đúng ngôn ngữ câu hỏi
8. **Kiểm tra mâu thuẫn** — phát hiện thông tin trái chiều giữa các nguồn (optional)

Câu trả lời kèm theo: danh sách tài liệu nguồn, score, và các bước agent đã thực hiện.

**Giới hạn:** Hệ thống chỉ trả lời dựa trên tài liệu đã nạp. Câu hỏi về thông tin chưa có trong kho sẽ không được trả lời chính xác.

---

### 3.2 Search — Tìm kiếm tài liệu

Tìm kiếm thuần túy, không qua bước tổng hợp LLM:
- Hybrid search: vector (semantic) + BM25 (keyword)
- Scoring: 5 signals có trọng số (semantic 0.5, BM25 0.3, graph 0.2, recency 0.1, popularity 0.1)
- Source weighting: Confluence > Jira > File Server > Slack (theo độ tin cậy nguồn)
- Kết quả là danh sách chunks có liên quan, kèm điểm số và đường dẫn nguồn

---

### 3.3 Connectors — Thu thập tài liệu

Hệ thống kết nối và đồng bộ tài liệu từ:

| Nguồn | Khả năng | Cấu hình cần |
|---|---|---|
| **Jira** | Pull issues, comments, attachments | JIRA_URL, API token |
| **Confluence** | Pull pages, parse HTML theo section | CONFLUENCE_URL, API token |
| **Slack** | Pull messages theo channel | SLACK_BOT_TOKEN |
| **File Server (SMB)** | Pull files từ Windows shared folder | SMB_HOST, credentials |

**Incremental sync:** Mỗi lần chạy, hệ thống chỉ lấy tài liệu mới hơn lần sync cuối (không lấy lại toàn bộ).

**Luồng xử lý mỗi tài liệu sau khi fetch:**
1. Làm sạch text
2. Download và OCR/caption hình ảnh (nếu Vision enabled)
3. Trích xuất entities (tên người, tech stack, Jira key, project...)
4. Nhận dạng danh tính (merge cùng người có nhiều aliases)
5. Chunking (section-aware cho Confluence)
6. Tạo vector embedding + lưu vào Qdrant
7. Index keyword vào PostgreSQL
8. Cập nhật Knowledge Graph

---

### 3.4 Knowledge Graph — Đồ thị tri thức

**Chứa gì:** Entities (người, công nghệ, project...) và quan hệ `co_occurs` giữa chúng, kèm trọng số (weight = số lần cùng xuất hiện trong document).

**Dùng để làm gì:**
- **GraphRAG**: trong quá trình search, hệ thống dùng entities từ top results để "hop" sang các documents liên quan qua graph — tìm được tài liệu không match từ khóa nhưng có liên quan về mặt knowledge.
- **Visualize**: Frontend render đồ thị để user thấy mối quan hệ giữa các khái niệm.

**Identity Resolution:** Hai node `nguyen.van.a@company.com` và `@nguyena` (Slack handle) được tự động merge thành cùng một entity "person" nếu đủ bằng chứng (email match, account ID match...).

**Trạng thái:** Implement dựa trên PostgreSQL (SQL queries). Entity extraction dựa trên regex + pattern matching, không phải ML model chuyên biệt.

---

### 3.5 AI Task Drafts — Quản lý task từ tín hiệu nội bộ

Hệ thống tự động scan Slack và Confluence để phát hiện tín hiệu công việc cần tạo Jira task:

```
Scan (Slack/Confluence) → AI Extract (title, type, priority, assignee)
→ Draft "pending" → PM/PO review & confirm → Submit to Jira
→ Jira key lưu vào DB → Sync Jira status định kỳ
```

**Scope-based access:** Mỗi draft được gán `scope_group_id`. Người dùng chỉ thấy draft thuộc group của mình. Admin thấy tất cả.

**Tích hợp Jira:** Tạo issue thực trên Jira, lưu lại `jira_key`. Có cơ chế sync trạng thái Jira về DB.

---

### 3.6 SDLC Document Drafts — Soạn thảo tài liệu AI

Người dùng yêu cầu AI tạo bản nháp tài liệu (SRS, BRD, Test Plan, ADR...) từ:
- Câu trả lời Chat AI (kèm nguồn tài liệu)
- Documents được chọn thủ công (tối đa 12)

**Các loại tài liệu hỗ trợ:** SRS, BRD, Use Cases, User Stories, Gherkin AC, Architecture Decision Record (ADR), API Contract, Test Cases (5 levels), Deployment Runbook, Release Notes, v.v.

**Luồng xử lý:**
1. API tạo "stub" draft (status: `processing`)
2. Job được enqueue vào queue `arq:ai` (timeout 25 phút)
3. `worker_ai` chạy LLM → tạo Markdown content + structured JSON (glossary, actors, rules) bao bọc trong `<json>...</json>`
4. Hệ thống tự trích xuất và lưu vào **Project Memory** (glossary, actor, rule)
5. Draft cập nhật status `done`, frontend polling nhận kết quả

**AI Refine:** Người dùng chọn một đoạn text trong draft → nhập hướng dẫn → AI viết lại đoạn đó (không tạo lại toàn bộ).

---

### 3.7 Auto Work (SDLC Suite — 9 bước)

Luồng phức tạp nhất: người dùng nhập yêu cầu nghiệp vụ, hệ thống chạy chuỗi 9 AI agent:

| Bước | Agent | Output |
|---|---|---|
| 1 | Requirement Analyst | FR, NFR, BR, Assumptions, Intake JSON |
| 2 | Architect Reviewer | Logic Review, Permission Model, Edge Cases |
| 3 | Solution Designer | Architecture, ADR, API Contract, Data Model |
| 4 | Document Writer | SRS, BRD, Use Cases, Validation Rules |
| 5 | User Story Writer | User Stories, Gherkin AC, INVEST, DoD |
| 6 | FE Technical Spec | Component Tree, UI State, a11y, Perf Budget |
| 7 | QA Reviewer | Test Cases (5 levels), OWASP, UAT Matrix |
| 8 | Deployment Spec | CI/CD, Monitoring, Runbook, DR Plan |
| 9 | Change & Release Mgr | CR, Impact Analysis, Release Notes, Risk Log |

**Thời gian xử lý:** Phụ thuộc vào tốc độ Ollama trên máy host. Thực tế có thể 10-30+ phút.

**Cảnh báo:** Output là bản nháp tham khảo. Cần review kỹ trước khi dùng chính thức.

---

### 3.8 Skill Prompts — Tuỳ chỉnh prompt AI

Admin/Knowledge Architect có thể chỉnh sửa system prompt cho từng loại tài liệu trong DB. Prompt tuỳ chỉnh được ưu tiên hơn prompt mặc định khi tạo draft.

---

### 3.9 Project Memory — Bộ nhớ dự án

Hệ thống tự động trích xuất và lưu từ mỗi lần tạo draft:

| Loại | Ví dụ |
|---|---|
| Glossary | `"Sprint" = "chu kỳ phát triển 2 tuần"` |
| Actor/Stakeholder | `"PM" = "Nguyễn Văn A, quản lý sprint"` |
| Business Rule | `"BR-01" = "Người dùng phải xác thực email trước khi..."`  |

Những thông tin này được inject vào context của các draft tiếp theo (với ràng buộc "DO NOT redefine") để đảm bảo nhất quán thuật ngữ.

---

### 3.10 AI Workflows

Module đang phát triển — cho phép tạo và chạy custom workflow nhiều bước AI. Chưa có đánh giá chính thức về tính năng.

---

## 4. Phân quyền người dùng

### 4.1 Backend (thực thi tại server)

| Điều kiện | Endpoint được bảo vệ |
|---|---|
| Có JWT hợp lệ | Hầu hết API |
| role = `system_admin` hoặc `is_admin=True` | Ingest trigger, Jira sync admin, user management |
| role = `pm_po` hoặc `ba_sa` (hoặc admin) | Confirm/submit/scan task drafts |

### 4.2 Frontend (UI control bổ sung)

| Role | Modules hiển thị |
|---|---|
| `system_admin` | Tất cả |
| `knowledge_architect` | Chat, Search, Documents, Graph, Skill Prompts, Memory |
| `pm_po` | Thêm: Tasks, Drafts, SDLC Suite, Workflows |
| `ba_sa` | Thêm: Tasks, Drafts, SDLC Suite, Workflows |
| `dev_qa` | Chat, Search, Documents, Graph, Tasks |
| `standard` | Chat, Search, Documents, Graph |

---

## 5. Dữ liệu và bảo mật

- **LLM chạy local** qua Ollama — dữ liệu không gửi ra cloud.
- **Embedding chạy local** qua Ollama — không dùng API bên ngoài.
- **Connectors** (Jira, Confluence, Slack) pull data về lưu local — dữ liệu từ các service đó sẽ rời khỏi service nhưng không ra ngoài hạ tầng nội bộ.
- **JWT Secret** mặc định là `"change-me-in-production"` — **bắt buộc** phải đổi trước khi deploy.
- **CORS** hiện set `allow_origins=["*"]` — cần giới hạn lại trong production.

---

## 6. Tích hợp bên ngoài

| Service | Mục đích | Bắt buộc? |
|---|---|---|
| Ollama | LLM inference + text embedding | **Bắt buộc** cho mọi tính năng AI |
| PostgreSQL | Database chính (documents, users, drafts, graph) | **Bắt buộc** |
| Qdrant | Vector search + semantic cache | **Bắt buộc** |
| Redis | Background job queue (arq) | **Bắt buộc** cho drafting async |
| Jira | Nguồn tài liệu + tạo task | Tuỳ chọn |
| Confluence | Nguồn tài liệu | Tuỳ chọn |
| Slack | Nguồn tài liệu + task signals | Tuỳ chọn |
| SMB File Server | Nguồn tài liệu | Tuỳ chọn |

---

## 7. Hạn chế và thực tế cần biết

| Hạn chế | Chi tiết |
|---|---|
| **Tốc độ** | LLM local chậm. SDLC 9 bước có thể mất 10-30 phút. Drafting thường mất 2-5 phút. |
| **Chất lượng** | Phụ thuộc vào model Ollama, chất lượng tài liệu đầu vào, và prompt tuning. |
| **Không production-ready** | JWT Secret mặc định, CORS mở, chưa có test suite đầy đủ. |
| **Không có HA** | Không có load balancing, replica, hay failover. |
| **Vision** | Mặc định tắt. Cần cài riêng vision model (llava-phi3 hoặc tương đương). |
| **Cross-Encoder Reranker** | Mặc định dùng LLM reranker. Cross-Encoder cần tải model HuggingFace xuống local. |
