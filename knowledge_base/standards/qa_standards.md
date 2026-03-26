# Khung thực thi Kiểm thử & QA (QA Execution Framework - Hardened) — Knowledge Platform

Tài liệu này không chỉ là tiêu chuẩn, mà là **bộ khung thực thi** bắt buộc để đảm bảo chất lượng hệ thống Knowledge Platform từ mức mã nguồn đến trải nghiệm người dùng cuối.

## 1. Mapping Chiến lược theo Module (System Mapping Layer)
Mọi tính năng quan trọng phải có chiến lược kiểm thử đặc thù:

| Module | Chiến lược Trọng tâm | Metrics / Validation |
| :--- | :--- | :--- |
| **Chat AI & RAG** | Timeout, Streaming integrity, Token limit | Latency < 5s (P95), No broken stream |
| **Document Upload** | File size (max 50MB), Format, Queue retry | 100% file in queue processed |
| **Authentication** | Brute force, Session expiry, Role conflict | Zero unauthorized access |
| **Admin Management** | Data integrity, Large list loading | Render < 2s for 1000 items |

## 2. Chỉ số Chất lượng Cụ thể (Concrete Metrics Layer)
Không nói "nhanh" hay "tốt", mọi kết quả test phải so sánh với Baseline:
- **Performance (SLA)**: 
  - API Response Time < 500ms (Internal), < 2s (Third-party integrations).
  - Error Rate < 0.1% trong điều kiện tải bình thường.
- **Load/Stress Testing**:
  - **Goal**: 100 concurrent users (Hệ thống hiện tại).
  - **Tool**: k6 hoặc Locust. Baseline được lấy từ bản release ổn định gần nhất.
- **Chaos Engineering**: Chỉ thực hiện trên Staging.
  - **Target**: Kill Redis hoặc Worker service.
  - **Success**: Hệ thống không sập toàn bộ, tự động phục hồi (Self-healing) trong < 30s.

## 3. Điều kiện Tiên quyết cho Automation (Automation-Ready)
Để bộ script (Playwright/Pytest) không bị fail sau 2 sprint, bắt buộc:
- **Data Seeding**: Phải có script `seed_test_data.py` để tạo môi trường sạch (Clean state) trước mỗi phiên test.
- **UI Test-IDs**: Dev bắt buộc gắn attribute `data-testid` cho mọi interactive element (Button, Input, Modal).
- **API Stability**: API Contract (OpenAPI) phải được freeze 48h trước khi viết script Automation.

## 4. Quản trị Truy vết (Traceability Governance)
Để chuỗi `BR ↔ FR ↔ UC ↔ TC` không trở thành "giấy rác":
- **Tooling**: Sử dụng **Jira** để liên kết Ticket (Story) với Test Case (X-ray hoặc TestRail).
- **Maintenance**: Khi Requirement (BR) thay đổi, BA Lead và QA Lead phải họp review Change Impact trong vòng 24h để cập nhật lại chain.
- **Sign-off**: Mỗi bản release phải đính kèm báo cáo Coverage từ ma trận truy vết (Dưới 95% coverage = No Go).

## 5. Shift-left & Quality Gates Execution
- **Reviewer**: QA tham gia review Code PR liên quan đến tính năng core để check test coverage.
- **Gate 1 (Internal)**: 100% Unit Test pass + Zero linting errors.
- **Gate 2 (Staging)**: 100% Automation Regression pass + 0 Critical bugs.
- **Gate 3 (UAT)**: Stakeholder Sign-off + Documentation (Release Notes) hoàn thiện.

---
*Cập nhật lần cuối: 2026-03-26 bởi Knowledge Sub-agent (Execution-ready Hardening)*

---
*Cập nhật lần cuối: 2026-03-26 bởi Knowledge Sub-agent*
