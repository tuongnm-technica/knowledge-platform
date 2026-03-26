# Khung thiết kế Hệ thống thực chiến (SA Execution Framework - Production Ready)

Tài liệu này định nghĩa các chuẩn mực thiết kế "Battle-hardened" cho Knowledge Platform, đảm bảo hệ thống không chỉ chạy đúng mà còn sống sót và tối ưu tài chính trong môi trường Production thực tế.

## 1. Benchmark Assumptions (Ngữ cảnh hiệu năng)
Mọi chỉ số Metric chỉ có giá trị khi đi kèm giả định phần cứng và payload:
- **Node Spec**: Giả định tối thiểu **2 CPU / 4GB RAM** cho mỗi service instance.
- **Payload Context**:
  - **Normal Request**: < 10KB (Metadata, Chat text). Target: **200 RPS**.
  - **Heavy Request**: 5MB - 50MB (PDF/Document upload). Target: **10 RPS**.
  - **AI Processing**: Latency ~5s - 30s tùy độ dài token.

## 2. Bottleneck & Scaling Strategy
SA phải xác định trước điểm nghẽn để có kế hoạch Scale-out:
- **Primary Bottleneck**: **Database (I/O & Connections)** là điểm nghẽn đầu tiên khi tải ghi cao (Write-heavy). 
  - *Strategy*: Tăng Connection Pool và áp dụng Read-replicas nếu > 500 RPS.
- **Secondary Bottleneck**: **Worker nodes** khi xử lý AI/OCR dồn dập.
  - *Strategy*: Auto-scale Worker nodes dựa trên chỉ số `Queue Depth` (Threshold > 500 jobs).

## 3. Async Consistency & State Machine
Để tránh mất đồng bộ giữa DB, S3 và Worker:
- **Consistency Model**: Chấp nhận **Eventual Consistency** cho các tác vụ xử lý tài liệu.
- **Status State Machine**: Bắt buộc workflow: `PENDING` -> `PROCESSING` -> `DONE` hoặc `FAILED`.
- **Atomic Operation**: Ghi DB record trước khi đẩy job vào Queue. Nếu đẩy queue fail, phải có cơ chế retry ghi queue hoặc rollback DB.

## 4. Resilience: Retry Strategy & DLQ
Tuyệt đối không để mất Job quan trọng:
- **Retry Policy**: Áp dụng **Exponential Backoff** (với jitter). Ví dụ: 1s, 10s, 1m, 10m.
- **Dead-Letter Queue (DLQ)**: Mọi job thất bại sau 5 lần retry phải được đẩy vào DLQ để kỹ thuật viên can thiệp thủ công (Manual intervention).
- **Circuit Breaker**: Ngắt kết nối AI API nếu Error Rate từ Provider > 30% trong 1 phút để bảo vệ tài nguyên hệ thống.

## 5. Security & Observability (Hardened)
- **Authorization**: Sử dụng **OAuth2 + JWT** (RS256). Áp dụng **RBAC** (Role-based Access Control) chặt chẽ đến từng resource ID.
- **Distributed Tracing**: Tích hợp **OpenTelemetry (Osh) / Jaeger**. Trace-id phải xuyên suốt từ Client -> API -> Queue -> Worker -> DB.
- **Input Validation**: Chặn mọi SQL Injection/XSS tại tầng Gateway (Pydantic + Logic validation).

## 6. AI Cost Awareness & Guardrails
Bảo vệ tài chính cho hệ thống AI:
- **Token Guardrail**: Max 4000 tokens/request cho đầu vào người dùng.
- **Rate Limit per User**: Giới hạn số request AI/phút cho từng User (ví dụ: 10 req/min) để tránh phá hủy budget.
- **Budget Alerts**: Cảnh báo Slack/Telegram khi chi phí AI vượt 80% hạn mức ngày.

---
*Cập nhật lần cuối: 2026-03-26 bởi Knowledge Sub-agent (Production-ready Hardened)*
