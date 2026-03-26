# Khung thực thi Thiết kế Giải pháp (Solution Design Execution Spec - Hardened)

Tài liệu này không chỉ là nguyên lý, mà là **bộ quy tắc thực thi (Enforcement Rules)** bắt buộc. Mọi bản thiết kế giải pháp (Solution Design) chỉ được phê duyệt khi đáp ứng đầy đủ các tiêu chuẩn này.

## 0. Definition of Done (DoD) cho Solution Design
Một bản thiết kế được coi là "Xong" khi có đầy đủ:
- [ ] **Runtime Spec**: Timeout, Retry, Fallback cho mọi kết nối ngoại vi.
- [ ] **Data Ownership**: Xác định rõ Service nào sở hữu bảng nào, quy tắc đọc/ghi chéo.
- [ ] **Failure Design**: Sơ đồ xử lý lỗi (CB, DLQ) cho các luồng chính.
- [ ] **Observability Spec**: Danh sách Log fields và Trace point format.
- [ ] **ADR Mapping**: Link tới các quyết định kiến trúc liên quan.

## 1. Runtime Behavior & Failure Design (Production-Ready)
Không để hệ thống "chết lặng" khi quá tải:
- **Timeout Standard**: 
  - Internal API: < 500ms.
  - Third-party (AI/OCR): 30s - 60s (phải xử lý async).
- **Retry Strategy**: 100% Async job phải dùng **Exponential Backoff with Jitter**. Không retry cho lỗi 4xx.
- **Circuit Breaker (CB)**: Threshold: 20 failures trong 10s -> Open. Fallback: Trả về dữ liệu từ Cache hoặc thông báo "Service tạm gián đoạn".
- **Bulkhead Isolation**: Tách biệt Thread pool cho các tác vụ nặng (xử lý file) để không làm nghẽn API login/chat.

## 2. API Execution & Idempotency
- **Pagination**: Mặc định dùng **Cursor-based pagination** cho các danh sách lớn hoặc dữ liệu thay đổi liên tục. Chỉ dùng Offset cho danh sách tĩnh < 1000 items.
- **Idempotency Execution**:
  - **Storage**: Lưu `Idempotency-Key` vào **Redis** với TTL = 24h.
  - **Conflict**: Trả về `409 Conflict` nếu key đang được xử lý hoặc `200/201` kèm kết quả cũ nếu đã xử lý xong.
- **Rate Limiting**: Thực thi tại Gateway theo `user_id` và `ip_address`. Limit: 100 req/min (Normal), 5 req/min (Heavy AI).

## 3. Data Ownership & Cache Strategy
- **Ownership**: Chỉ service chủ quản được quyền Write vào DB của mình. Các service khác chỉ được Read qua API hoặc Message Queue.
- **Cache Invalidation**: Ưu tiên **Cache-aside pattern**. 
  - **Invalidation**: Xóa Cache ngay khi DB Update thành công (Post-commit). 
  - **Stale Data**: Chấp nhận dữ liệu cũ tối đa 60s cho các module không critical.
- **Transaction Boundary**: Không kéo dài Transaction quá 2s. Tránh Distributed Transaction; ưu tiên **Saga/Outbox pattern** cho tính nhất quán async.

## 4. Security Architecture Layer
- **Auth Flow**: Sử dụng **OpenID Connect (OIDC)** hoặc OAuth2 với PKCE cho Frontend.
- **Secret Management**: Tuyệt đối không dùng `.env` trên Production. Phải dùng **HashiCorp Vault** hoặc **AWS/GCP Secret Manager**.
- **Audit Log**: Mọi hành động `Create/Update/Delete` trên dữ liệu nhạy cảm phải log: `user_id`, `timestamp`, `action`, `resource_id`, `old_value`, `new_value`.

## 5. Observability Spec (Chi tiết)
- **JSON Log Fields**: Bắt buộc có `trace_id`, `span_id`, `env`, `service_name`, `error_code`, `response_time_ms`.
- **Trace Propagation**: Sử dụng tiêu chuẩn **W3C Trace Context**. Trace ID phải được truyền từ Frontend xuống tận Database query logs.
- **Metric Naming**: Theo chuẩn Prometheus: `service_name_module_action_total/duration_ms`.

---
*Cập nhật lần cuối: 2026-03-26 bởi Knowledge Sub-agent (Execution Spec Hardened)*
