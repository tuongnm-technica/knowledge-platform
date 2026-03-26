# Khung thực thi Phân tích Nghiệp vụ (BA Execution Framework - Hardened) — Knowledge Platform

Tài liệu này định nghĩa phương pháp thực thi BA thực chiến, đảm bảo mọi yêu cầu đều "sạch", có tính thực thi và dễ dàng quản lý thay đổi.

## 1. Mapping Phân tích theo Module (Analysis Mapping Layer)
BA phải phân tích sâu cho từng module trọng tâm:

| Module | Tài liệu Trọng tâm | Quy tắc "Ép chết" (Enforcement) |
| :--- | :--- | :--- |
| **RAG Retrieval** | Business Rules (BR) | Định nghĩa rõ độ ưu tiên nguồn dữ liệu (Source Priority) |
| **Auth & Security** | Use Case (UC) | Phải có State Machine: `Inactive -> Active -> Expired` |
| **Knowledge Base** | Glossary | 100% thuật ngữ chuyên ngành phải có Approval của Stakeholder |
| **AI Workflows** | Exception Flows | Phải bao phủ 100% kịch bản "AI không trả kết quả" |

## 2. Tiêu chuẩn "Full Testability" (Gherkin-style)
Mọi Functional Requirement (FR) phải đạt chuẩn **Gherkin** để QA có thể auto-gen test case:
- **Nguyên tắc**: `GIVEN [Pre-condition] + WHEN [Action] + THEN [System Response]`.
- **Enforcement**: Tài liệu SRS thiếu Gherkin cho các tính năng core sẽ bị QA từ chối (Reject) ngay tại Quality Gate 1.

## 3. Quản trị Business Rules (BR) & Versioning
- **Versioning**: Sử dụng bảng **BR-Version-History**. Mỗi thay đổi BR phải tăng minor version (1.0 -> 1.1).
- **Tooling**: Quản lý BR tập trung trên **Confluence/Notion** hoặc **Jira Assets** để mọi Dev/QA đều truy cập được bản mới nhất.
- **Conflict Handling**: Rule có Priority cao hơn (Ví dụ: Luật pháp > Chính sách công ty) luôn được ưu tiên.

## 4. Maintenance & Traceability (Jira Integration)
Để Traceability Matrix không thành "giấy rác":
- **Mapping**: Link trực tiếp Test Case (Jira Issue) vào Requirement (User Story) sử dụng `is tested by` link.
- **Change Impact SLA**: Khi có thay đổi BR, BA Lead phải hoàn thành bảng phân tích tác động (Impact Matrix) trong vòng **24h** và tag tất cả Lead Dev/QA liên quan.

## 5. Glossary Governance (Owner & Flow)
- **Owner**: QA Lead và BA Lead là đồng chủ sở hữu (Co-owners).
- **Conflict Flow**: Khi có mâu thuẫn thuật ngữ, BA Lead là người đưa ra quyết định cuối cùng dựa trên phản hồi của Stakeholder.
- **Strictness**: Code review sẽ bắt lỗi nếu tên biến (Variable naming) đặt sai lệch so với Glossary đã thống nhất.

---
*Cập nhật lần cuối: 2026-03-26 bởi Knowledge Sub-agent (Senior BA Execution-ready)*

---
*Cập nhật lần cuối: 2026-03-26 bởi Knowledge Sub-agent (Incorporate Senior BA Review)*

---
*Cập nhật lần cuối: 2026-03-26 bởi Knowledge Sub-agent*
