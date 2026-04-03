# Hướng dẫn Sử dụng Module AI Workflows

Hệ thống **AI Workflows** là một công cụ mạnh mẽ cho phép bạn thiết kế, tùy chỉnh và tự động hóa các quy trình làm việc phức tạp bằng cách kết hợp nhiều bước (Nodes) xử lý AI khác nhau.

---

## 1. AI Workflows có thể làm được gì?

Thay vì chỉ hỏi-đáp (Chat) thông thường, AI Workflows cho phép bạn xây dựng các "dây chuyền sản xuất nội dung" chuyên nghiệp:

*   **Kết nối dữ liệu nội bộ (RAG):** Tự động tìm kiếm thông tin từ Knowledge Base (PDF, Confluence, Slack...) để đưa vào quy trình xử lý.
*   **Chuỗi suy luận đa bước:** Kết quả của bước trước là đầu vào của bước sau (ví dụ: Tìm kiếm -> Tóm tắt -> Dịch thuật -> Viết báo cáo).
*   **Định dạng chuyên sâu:** Sử dụng node **Doc Writer** để xuất bản các tài liệu chuẩn Markdown.
*   **Xuất bản tài liệu chuyên nghiệp:** Node **DOCX/PPTX Export** giúp chuyển đổi nội dung từ AI thành tệp tin Word và PowerPoint thực thụ với định dạng cao cấp.
*   **Thư ký ảo (Notification):** Tự động gửi kết quả báo cáo qua **Slack** hoặc **Email** ngay khi hoàn thành, kèm theo tệp đính kèm thông minh.
*   **Theo dõi thời gian thực:** Quan sát từng Agent làm việc và xem kết quả trả về ngay lập tức cho từng công đoạn.

---

## 2. Các thành phần chính của quy trình

Mỗi Workflow được cấu thành từ các **Node (Nút xử lý)**:

*   **LLM Node:** Sử dụng trí tuệ nhân tạo để phân tích, sáng tạo hoặc biến đổi văn bản.
*   **RAG Node:** Tự động truy xuất dữ liệu từ kho tri thức của công ty dựa trên ngữ cảnh hiện tại.
*   **Doc Writer Node:** Tối ưu để viết các tài liệu dài (SRS, SA...) dưới định dạng Markdown.
*   **Export Node (New):** Chuyển đổi Markdown thành file `.docx` (Word) hoặc `.pptx` (PowerPoint).
*   **Notification Node (New):** Gửi thông báo qua Slack hoặc Email (Hỗ trợ đính kèm file tự động).

---

## 3. Xem trước cao cấp (Premium Preview)

Trước khi tải tài liệu về máy, bạn có thể nhấn nút **Preview** trên kết quả của Node Export:
-   **Chế độ A4:** Giả lập văn bản in ấn thực tế (giống hệt bản in Word).
-   **Chế độ Slide:** Giả lập bản trình chiếu 16:9 chuyên nghiệp.
Tính năng này giúp bạn kiểm tra bố cục và nội dung "offline" ngay trên trình duyệt mà không tốn tài nguyên tải về.

---

## 4. Biến đặc biệt: {{START}} là gì?

`{{START}}` là **biến khởi đầu** quan trọng nhất trong mọi Workflow.

Khi bạn nhấn nút **Run** trên một Workflow, hệ thống sẽ hiện ra một ô nhập liệu (Input). Toàn bộ nội dung bạn nhập vào ô đó sẽ được gán vào biến `{{START}}`.
*   **Vị trí:** Thường được dùng ở **Node đầu tiên** để kích hoạt quy trình.
*   **Tác dụng:** Nó đóng vai trò là "nguyên liệu thô" để các Agent bắt đầu làm việc.

---

## 5. Các loại Trình kích hoạt (Trigger Classes)

1.  **Manual (Thủ công):** Chạy khi bạn nhấn nút Run.
2.  **Scheduled (Đặt lịch):** Tự động chạy theo định kỳ (ví dụ: mỗi sáng thứ Hai lúc 8h). Sử dụng cú pháp Cron (ví dụ: `0 8 * * 1`).
3.  **Webhook (API):** Chạy khi có tín hiệu từ các ứng dụng bên ngoài (Jira, Slack, hoặc script của riêng bạn).

---

## 6. Hướng dẫn sử dụng chi tiết

### Bước 1: Tạo Workflow mới
1.  Truy cập menu **AI Workflows** ở vị trí mới tại mục **Workspace**.
2.  Nhấn nút **+ Create Workflow**.

### Bước 2: Thiết kế các Node
1.  **Node 1 (Bắt đầu):** Sử dụng `{{START}}`.
2.  **Node 2 (Xử lý):** Sử dụng `{{node_1_output}}`.
3.  **Node cuối (Xuất bản/Thông báo):** Chọn loại `docx_export` hoặc `email_notify` để hoàn thành quy trình.

---

## 7. Các ví dụ nâng cao (Advanced Examples)

### Ví dụ 1: Hệ thống Soạn thảo Đề xuất Dự án (Bidding Proposal)
*   **Node 1 (RAG):** Tìm Case Study Fintech tương tự.
*   **Node 2 (Doc Writer):** Viết bản đề xuất hoàn chỉnh.
*   **Node 3 (DOCX Export):** Tạo file Word chuyên nghiệp.

### Ví dụ 2: Thư ký buổi sáng (AI Secretary - Daily Briefing) 🔔
*   **Node 1 (RAG):** Quét các task Jira và tin nhắn Slack trong 24h qua.
*   **Node 2 (LLM):** Tổng hợp top 3 việc quan trọng nhất.
*   **Node 3 (Slack Notify):** Gửi trực tiếp vào channel của bạn lúc 8:00 mỗi sáng.

### Ví dụ 3: Báo cáo Tiến độ Dự án (Manager Report) 📉
*   **Node 1 (RAG):** Thu thập dữ liệu tiến độ từ Jira.
*   **Node 2 (LLM):** Viết bản tin vắn cho quản lý (Rủi ro, Tiến độ, Kế hoạch).
*   **Node 3 (Email Notify):** Tự động gửi Email kèm file Word báo cáo chi tiết đính kèm.

---
> [!TIP]
> Bạn có thể sử dụng các **Templates** có chữ 📅 hoặc 📈 để bắt đầu nhanh với chế độ Thư ký tự động!
