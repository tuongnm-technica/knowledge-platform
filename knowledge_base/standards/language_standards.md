# Tiêu chuẩn Ngôn ngữ & Bản địa hóa (Language & Localization Standards) — Knowledge Platform

Bộ tri thức này định nghĩa các chuẩn mực về ngôn ngữ (Vietnamese, English, Japanese) và kỹ thuật bản địa hóa tại Knowledge Platform, đảm bảo tài liệu và sản phẩm có tính toàn cầu và chuyên nghiệp.

## 1. Tiêu chuẩn Tiếng Việt (Vietnamese Standard)
- **Văn phong**: Sử dụng văn phong chuyên nghiệp, khách quan (hành chính - kỹ thuật).
- **Thuật ngữ**: Ưu tiên thuật ngữ chuyên ngành đã được chuẩn hóa (ví dụ: "Tính nhất quán" thay vì "Sự giống nhau").
- **Nhất quán**: Luôn kiểm tra sự thống nhất giữa thuật ngữ Tiếng Việt và thuật ngữ Tiếng Anh đi kèm trong ngoặc đơn ở lần đầu xuất hiện.

## 2. Tiêu chuẩn Tiếng Anh (English Standard)
- **Precision**: Sử dụng các động từ chỉ thị mạnh (Must, Shall, Should, Will) theo chuẩn RFC 2119.
- **Terminology**: Tuân thủ thuật ngữ chuẩn của các framework (FastAPI, React) và các chuẩn công nghiệp (RESTful, OAuth2).
- **Grammar**: Đảm bảo ngữ pháp chính xác, câu văn ngắn gọn, súc tích, tránh mơ hồ.

## 3. Tiêu chuẩn Tiếng Nhật (Japanese Standard - IT)
- **Keigo (Kính ngữ)**: Sử dụng Desu/Masu (Desu/Masu-tai) cho tài liệu hướng dẫn và Teinei-go (Lịch sự) cho giao tiếp nghiệp vụ.
- **Katakana Implementation**: Sử dụng Katakana chính xác cho các thuật ngữ mượn từ Tiếng Anh (ví dụ: ログイン - Login, ユーザー - User).
- **Định dạng tài liệu**: Tuân thủ các quy chuẩn trình bày tài liệu kỹ thuật của Nhật Bản (IT specification standards).

## 4. Bản địa hóa & Đa ngôn ngữ (L10n & i18n)
- **Character Encoding**: Luôn sử dụng UTF-8 cho mọi ngôn ngữ.
- **Date/Time Formatting**: 
  - VN: dd/mm/yyyy
  - US: mm/dd/yyyy hoặc yyyy-mm-dd
  - JP: yyyy年mm月dd日
- **Currency & Units**: Chuyển đổi linh hoạt giữa VNĐ, USD, JPY và các đơn vị đo lường tương ứng.

## 5. Quy tắc Dịch thuật Kỹ thuật (Technical Translation)
- **Context Awareness**: Không dịch word-by-word. Phải hiểu ngữ cảnh kỹ thuật trước khi chuyển ngữ.
- **Glossary First**: Luôn đối chiếu với Glossary của dự án để đảm bảo tính nhất quán xuyên suốt các ngôn ngữ.
- **Symbol & Punctuation**: Thống nhất cách sử dụng dấu câu (ví dụ: dấu phẩy, dấu chấm phẩy) theo quy chuẩn của từng ngôn ngữ.

---
*Cập nhật lần cuối: 2026-03-26 bởi Knowledge Sub-agent*
