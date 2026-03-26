# Tiêu chuẩn Phát triển Backend (BE Dev Execution Framework - Hardened)

Bộ tri thức này quy định các chuẩn mực thực thi Backend tại Knowledge Platform, đảm bảo tính an toàn, hiệu năng và khả năng phục hồi (Resilience) cao nhất.

## 1. Ngôn ngữ & Framework (Python + FastAPI)
- **Async I/O**: 100% tác vụ I/O (DB, Redis, External API) bắt buộc dùng `async/await`. Không block event loop.
- **Pydantic V2 Validation**: Sử dụng Pydantic để thực thi "Parse, don't validate". Mọi đầu vào phải được ép kiểu và sanitize nghiêm ngặt.
- **Dependency Injection**: Sử dụng FastAPI Depends để quản lý lifecycle của DB sessions và services.

## 2. Truy xuất Dữ liệu & Performance
- **Connection Pooling**: Cấu hình `pool_size` và `max_overflow` dựa trên Benchmark của SA (ví dụ: 20-50).
- **Atomic Operations**: Sử dụng DB transactions (`begin_nested` hoặc `transaction`) cho các chuỗi lệnh liên quan.
- **Query Hardening**: Cấm sử dụng `select *`. Luôn chỉ định rõ các cột cần lấy để tối ưu băng thông.

## 3. Worker & Resilience (Arq / Redis)
- **Retry Strategy**: Bắt buộc cấu hình `max_retries` với thuật toán **Exponential Backoff**. 
- **Dead-Letter Queue (DLQ)**: Mọi task thất bại phải được log vào bảng `failed_jobs` hoặc `DLQ` kèm theo traceback và input data để debug.
- **Idempotency Execution**: Sử dụng Redis lock hoặc DB unique constraint để đảm bảo một job không bị xử lý trùng lặp khi retry.

## 4. Security & Authentication (RBAC)
- **RS256 JWT**: Sử dụng mã hóa khóa bất đối xứng cho Token. 
- **Granular RBAC**: Kiểm tra quyền (Permissions) ở cấp độ hành động (ví dụ: `documents:write`, `ai:chat`) thay vì chỉ check role Admin/User.
- **Security Headers**: Cấu hình đầy đủ CORS, HSTS, và CSP tại tầng Middleware.

## 5. Observability (OpenTelemetry)
- **Distributed Tracing**: Tích hợp **OpenTelemetry SDK**. Mọi request phải khởi tạo một `Root Span` và truyền `trace_id` xuống các service/worker liên quan.
- **Health & Readiness**: Endpoint `/health` phải kiểm tra được tính sẵn sàng của cả PostgreSQL và Redis.
- **Structured JSON Logging**: Log format phải chuẩn JSON để các hệ thống ELK/Loki có thể parse được.

---
*Cập nhật lần cuối: 2026-03-26 bởi Knowledge Sub-agent (BE Production-ready Hardened)*
