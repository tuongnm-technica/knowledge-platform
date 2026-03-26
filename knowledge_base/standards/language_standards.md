# Khung thực thi Ngôn ngữ & Bản địa hóa (Language Execution Spec - Hardened)

Tài liệu này không chỉ là hướng dẫn dịch thuật, mà là **bản quy chuẩn ngôn ngữ kỹ thuật** để đảm bảo tính chuyên nghiệp và đồng bộ xuyên suốt hệ thống toàn cầu.

## 1. Tiêu chuẩn Tiếng Việt Kỹ thuật (Direct & Imperial Tone)
- **Văn phong**: Sử dụng câu mệnh lệnh trực tiếp, không sử dụng các từ hoa mỹ hoặc mơ hồ.
  - *Sai*: "Bạn có thể cân nhắc việc thêm các trường dữ liệu..."
  - *Đúng*: "Thực hiện bổ sung các trường dữ liệu bắt buộc sau..."
- **Chuẩn hóa Thuật ngữ**:
  - `Consistency` -> **Tính nhất quán** (Không dùng: Sự giống nhau).
  - `Integrity` -> **Tính toàn vẹn** (Không dùng: Sự nguyên vẹn).
  - `Implementation` -> **Thực thi/Triển khai** (Không dùng: Việc thực hiện).
  - `Validation` -> **Xác thực dữ liệu** (Không dùng: Kiểm tra đúng sai).

## 2. Tiêu chuẩn Tiếng Anh (RFC 2119 Normative)
- **Compliance**: Sử dụng từ khóa chuẩn theo **RFC 2119**:
  - `MUST`: Bắt buộc tuyệt đối.
  - `MUST NOT`: Cấm tuyệt đối.
  - `SHOULD`: Khuyến nghị mạnh mẽ nhưng có thể đánh đổi.
  - `SHALL`: Biểu thị yêu cầu về mặt hệ thống/hợp đồng.
- **Terminology Consistency**: Luôn sử dụng đúng tên riêng của công nghệ (ví dụ: `PostgreSQL` thay vì `Postgres`, `FastAPI` thay vì `fastapi`).

## 3. Tiêu chuẩn Tiếng Nhật (IT Professionalism)
- **Nghiệp vụ**: Sử dụng **Desu/Masu** kèm theo các thuật ngữ IT chuẩn Nhật (Standard IT Terms).
- **Katakana Governance**: Tuân thủ quy tắc `ー` (Chonkhe) cho các từ mượn từ Tiếng Anh theo tiêu chuẩn JIS (ví dụ: `サーバー` - Server, `コンピューター` - Computer).
- **Hỗ trợ Đa ngôn ngữ**: Mọi nhãn (Label) trên giao diện phải được quản lý qua file `i18n` `.json` (không được hardcode text trong UI).

## 4. Localization Checklist (Bắt buộc)
- **Encoding**: Luôn là **UTF-8 (Without BOM)**.
- **Timezone**: Mặc định hệ thống sử dụng **UTC**. Khi hiển thị cho người dùng, chuyển đổi theo Timezone cục bộ (mặc định VN là **ICT - UTC+7**).
- **Date/Time Display**: 
  - VN: `dd/mm/yyyy hh:mm` (24h format).
  - International: `yyyy-mm-dd hh:mm:ss` (ISO 8601).
- **Currency & Numerics**:
  - VN: Sử dụng dấu chấm `.` để phân cách hàng nghìn (ví dụ: 1.000.000 VNĐ).
  - US/Global: Sử dụng dấu phẩy `,` (ví dụ: 1,000,000 USD).

## 5. Quy trình Kiểm soát Ngôn ngữ (Linguistic Quality Gate)
- **Context Review**: Tài liệu dịch từ AI phải được con người review về ngữ cảnh chuyên môn trước khi phát hành (Internal Release).
- **Glossary Audit**: 100% thuật ngữ mới phải được định nghĩa vào **Project Glossary** chung trước khi áp dụng vào SRS hay Code.

---
*Cập nhật lần cuối: 2026-03-26 bởi Knowledge Sub-agent (Language Hardened)*
