# Khung thực thi Phân tích Nghiệp vụ (BA Execution Framework - Hardened) — Knowledge Platform

> [!CAUTION]
> **TÀI LIỆU TIÊU CHUẨN - TÁCH BIỆT NGHIỆP VỤ ĐỘC LẬP (ATRS & RAG)**
> Tài liệu này định nghĩa tiêu chuẩn cho các hệ thống khác nhau. 
> **LƯU Ý**: ATRS và RAG là hai thực thể ĐỘC LẬP. Tuyệt đối không tự ý liên kết hoặc gộp chung trừ khi có yêu cầu cụ thể từ người dùng.

Tài liệu này định nghĩa phương pháp thực thi BA thực chiến, đảm bảo mọi yêu cầu đều "sạch", có tính thực thi và dễ dàng quản lý thay đổi.

## 1. Mapping Phân tích theo Hệ thống (System-Specific Standards)
BA phải tuân thủ đúng các quy tắc đặc thù cho từng loại hệ thống:

### A. Hệ thống Nghiệp vụ (Ví dụ: ATRS)
| Thành phần | Tài liệu Trọng tâm | Quy tắc "Ép chết" (Enforcement) |
| :--- | :--- | :--- |
| **Field bắt buộc** | Functional Requirements | Phải có Gherkin: `GIVEN [Retrieval] + WHEN [Input Missing] + THEN [Prompt Form]` |
| **Trạng thái hiển thị** | Business Rules | Mặc định: `Gắn với xe / Công khai` (Phải tuân thủ stakeholder quy định) |

### B. Hệ thống Nền tảng (Ví dụ: RAG Retrieval)
| Thành phần | Tài liệu Trọng tâm | Quy tắc "Ép chết" (Enforcement) |
| :--- | :--- | :--- |
| **Nguồn dữ liệu** | Business Rules | Định nghĩa rõ độ ưu tiên nguồn (Source Priority) |
| **Xử lý AI** | Exception Flows | Phải bao phủ 100% kịch bản "AI không trả kết quả" |

## 2. Tiêu chuẩn Formatting Chung (General Formatting Standards)
- **Gherkin Mandate**: Mọi Functional Requirement (FR) phải có cấu trúc GIVEN/WHEN/THEN.
- **Atomic Rules**: Mỗi yêu cầu (BR/FR/NFR) chỉ chứa duy nhất một ý tưởng (Atomic).
- **Versioning**: Sử dụng bảng **BR-Version-History** để quản lý thay đổi (Tăng minor version: 1.0 -> 1.1).

## 3. Maintenance & Traceability (Jira Integration)
Để Traceability Matrix không thành "giấy rác":
- **Mapping**: Link trực tiếp Test Case vào Requirement sử dụng `is tested by` link.
- **Change Impact SLA**: BA Lead phải hoàn thành Impact Matrix trong vòng 24h khi có thay đổi nghiệp vụ.

---
*Cập nhật lần cuối: 2026-03-31 bởi Knowledge Sub-agent (Independent ATRS vs RAG Isolation)*
