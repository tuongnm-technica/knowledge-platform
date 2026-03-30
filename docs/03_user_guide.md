# Tài liệu Hướng dẫn Sử dụng — Knowledge Platform

> **Phiên bản:** 2.0 | **Ngày:** 2026-03-30  
> **Đối tượng:** Người dùng cuối — BA, PM, Dev, QA sử dụng hàng ngày

---

## 1. Truy cập & Đăng nhập

Mở trình duyệt, vào địa chỉ do admin cung cấp (ví dụ: `http://server-noi-bo:8000`).

Nhập **email** và **mật khẩu** → nhấn **Đăng nhập**.

> Hệ thống không có tính năng tự đăng ký. Liên hệ admin để được cấp tài khoản.

---

## 2. Giao diện chính

- **Sidebar trái:** Menu điều hướng. Các module bạn thấy **phụ thuộc vào role** của tài khoản.
- **Thanh tiêu đề:** Tên trang hiện tại, nút chuyển giao diện Sáng/Tối, nút Đăng xuất.
- **Nội dung chính:** Hiển thị trang đang chọn.

---

## 3. Chat AI

**Truy cập:** Sidebar → **Chat AI**

### Cách dùng cơ bản:
1. Gõ câu hỏi vào ô input ở dưới cùng
2. Nhấn **Send** hoặc **Enter**
3. Đợi hệ thống xử lý (có thể mất vài giây đến vài chục giây)
4. Câu trả lời hiển thị kèm danh sách tài liệu nguồn

### Hệ thống làm gì phía sau?
1. Kiểm tra cache — nếu câu hỏi tương tự đã hỏi trước, trả về ngay
2. Lập kế hoạch tìm kiếm (1-3 sub-queries)
3. Tìm kiếm song song trong kho tài liệu
4. Mở rộng kết quả qua đồ thị tri thức
5. Chấm điểm lại và chọn top results
6. Tự sửa nếu kết quả chưa đủ tốt (1 lần retry)
7. Tổng hợp câu trả lời bằng đúng ngôn ngữ bạn hỏi

### Lưu ý quan trọng:
- Câu trả lời chỉ dựa trên **tài liệu đã nạp vào hệ thống**. Không có tài liệu → không có câu trả lời tốt.
- **Luôn kiểm tra tài liệu nguồn** trước khi dùng kết quả cho công việc quan trọng.
- Hệ thống đôi khi mắc sai lầm — đây là công cụ hỗ trợ, không thay thế kiến thức chuyên môn.
- Câu hỏi tiếng Việt → trả lời tiếng Việt. Câu hỏi tiếng Anh → trả lời tiếng Anh.

### Tạo draft từ câu trả lời:
Sau khi nhận câu trả lời, bạn có thể nhấn nút **"Tạo tài liệu"** để yêu cầu AI soạn bản nháp tài liệu từ câu trả lời đó (xem mục **Drafts**).

---

## 4. Search (Tìm kiếm)

**Truy cập:** Sidebar → **Search**

Khác với Chat — Search trả về **danh sách đoạn tài liệu**, không qua bước tổng hợp AI.

Dùng Search khi:
- Muốn xem nội dung gốc, không qua AI diễn giải
- Tìm một đoạn cụ thể và muốn biết chính xác nguồn
- Muốn tìm nhanh không cần câu trả lời dài

Kết quả hiển thị kèm: điểm số, nguồn (Confluence/Jira/Slack...), và đường dẫn.

---

## 5. Documents (Kho tài liệu)

**Truy cập:** Sidebar → **Knowledge Base**

Xem, quản lý tài liệu đã được nạp vào hệ thống:
- Danh sách tất cả documents
- Xem nội dung chi tiết từng document
- Admin: xóa document không cần thiết

---

## 6. Connectors (Nguồn dữ liệu)

**Truy cập:** Sidebar → **Connectors** *(Admin)*

Cấu hình nguồn dữ liệu cho hệ thống thu thập tài liệu tự động.

### Thêm connector:
1. Nhấn **+ Add Connector**
2. Chọn loại: **Jira**, **Confluence**, **Slack**, **File Server (SMB)**
3. Nhập thông tin xác thực
4. Lưu → Nhấn **Sync** để bắt đầu thu thập

### Cơ chế sync:
- **Incremental:** Mỗi lần sync, hệ thống chỉ lấy tài liệu **mới hơn** lần sync cuối — không tải lại toàn bộ.
- Sync chạy ngầm (background), không cần giữ trình duyệt mở.
- Có thể theo dõi tiến độ qua trạng thái connector.
- Sync có thể bị huỷ: admin nhấn Cancel → hệ thống dừng sau batch hiện tại.

### Luồng xử lý sau khi fetch:
Làm sạch → OCR hình ảnh (nếu bật) → trích xuất entities → chunking → vector embedding → index → cập nhật Knowledge Graph.

---

## 7. Knowledge Graph

**Truy cập:** Sidebar → **Knowledge Graph**

Visualize đồ thị các thực thể (người, công nghệ, project...) và mối quan hệ giữa chúng trong tài liệu.

- Xem mối liên hệ giữa các khái niệm
- Tìm kiếm node theo tên
- Click node để xem chi tiết

> **Lưu ý:** Entity extraction dựa trên pattern matching, không phải ML model chuyên biệt. Độ chính xác phụ thuộc vào cấu trúc tài liệu đầu vào.

---

## 8. AI Task Drafts *(PM/PO, BA/SA)*

**Truy cập:** Sidebar → **AI Task Drafts**

Module này quản lý "task signals" được AI phát hiện từ Slack và Confluence, có thể submit lên Jira.

### Vòng đời một draft:

```
pending (AI tạo ra) → review → confirmed (PM chỉnh sửa) → submit → submitted (trên Jira)
```

### Các thao tác:

**Xem danh sách:**
- Bạn chỉ thấy drafts thuộc **nhóm của bạn** (scope-based). Admin thấy tất cả.

**Review và Confirm:**
1. Click vào draft muốn xem
2. Kiểm tra: title, description, issue_type, priority, assignee, epic, labels
3. Chỉnh sửa nếu cần → Nhấn **Confirm**

**Submit lên Jira:**
- Chỉ draft có status `confirmed` mới submit được
- Nhấn **Submit** → hệ thống tạo Jira issue thực
- `jira_key` được lưu lại, kèm đường dẫn trực tiếp đến Jira issue

**Reject:**
- Nhấn **Reject** nếu draft không hợp lệ

**Batch actions:**
- Chọn nhiều drafts → Confirm/Reject/Update cùng lúc

### Trigger scan thủ công:
- Nhấn **Scan** → chọn số ngày muốn scan (Slack và Confluence)
- Hệ thống sẽ phân tích lại nội dung mới và tạo thêm drafts

> Cần role **PM/PO** hoặc **BA/SA** để Confirm/Submit/Scan. Mọi role có thể Reject.

---

## 9. Drafts — Soạn thảo tài liệu AI *(PM/PO, BA/SA)*

**Truy cập:** Sidebar → **Drafts**

### 9.1 Tạo draft từ Chat answer
Sau khi Chat trả lời, nhấn **"Tạo tài liệu từ câu trả lời này"**:
1. Chọn loại tài liệu (SRS, BRD, Test Plan, ADR...)
2. Nhập tiêu đề (tùy chọn)
3. Nhấn **Tạo** → xử lý đồng bộ, kết quả trả về ngay

### 9.2 Tạo draft từ documents
1. Trong Drafts → nhấn **Tạo mới**
2. Chọn loại tài liệu
3. Tìm và chọn documents làm nguồn (tối đa **12 documents**)
4. Nhập mục tiêu/yêu cầu
5. Nhấn **Tạo** → hệ thống enqueue job ngầm (`status: processing`)
6. **Polling tự động** — trang tự cập nhật khi xong (timeout job 25 phút)

### 9.3 Chỉnh sửa draft
- **Edit thủ công:** Chỉnh Markdown trực tiếp
- **AI Refine:** Chọn một đoạn text → nhập hướng dẫn → AI viết lại đoạn đó
  - Ví dụ: *"Viết lại đoạn này bằng tiếng Việt, ngắn gọn hơn"*
  - AI chỉ viết lại đoạn được chọn, không thay đổi phần còn lại
- **Thay đổi status:** `draft` → `review` → `approved`

### 9.4 Các loại tài liệu có thể tạo
SRS, BRD, Use Cases, User Stories, Gherkin AC, Architecture Decision Record (ADR), API Contract, Data Model, Test Plan, Test Cases, Deployment Runbook, Release Notes, Change Request, Risk Log, QA Matrix, v.v.

> **Quan trọng:** Output là bản nháp đầu. Cần review kỹ — đặc biệt với tài liệu quan trọng.

---

## 10. Auto Work — SDLC Suite *(PM/PO, BA/SA)*

**Truy cập:** Sidebar → **Auto Work - Dashboard**

Tính năng điều phối chuỗi 9 AI agent để phân tích yêu cầu nghiệp vụ.

### Cách dùng:
1. Nhập mô tả yêu cầu nghiệp vụ vào ô **"Yêu cầu"**
2. Nhấn **"Bắt đầu tác vụ"**
3. Hệ thống tạo job ngầm → progress cards hiển thị dần: BA → SA → QA...
4. Sau khi hoàn tất: xem kết quả trong tabs **BA Document**, **SA Document**, **QA Document**

### Thời gian xử lý:
Phụ thuộc vào máy chạy Ollama. Thực tế **10-30+ phút** cho đủ 9 bước.

⚠️ **Không đóng tab trong khi chờ.** Polling sẽ dừng nếu mất kết nối.

> Output là bản nháp tham khảo ở bước đầu. Cần BA/SA review và bổ sung chi tiết nghiệp vụ.

---

## 11. Skill Prompts *(Knowledge Architect, Admin)*

**Truy cập:** Sidebar → **Skill Prompts**

Tuỳ chỉnh system prompt cho từng loại tài liệu:
- Xem prompt mặc định
- Chỉnh sửa để AI viết theo template riêng của công ty
- Reset về prompt mặc định nếu cần

---

## 12. Project Memory *(PM/PO, Knowledge Architect, Admin)*

**Truy cập:** Sidebar → **Project Memory**

Xem các khái niệm được hệ thống tự động học từ các drafts:

| Loại | Nội dung |
|---|---|
| **Glossary** | Thuật ngữ và định nghĩa dự án |
| **Actors** | Stakeholders và vai trò |
| **Business Rules** | Quy tắc nghiệp vụ |

Những thông tin này được inject vào context của mọi draft tiếp theo để đảm bảo nhất quán.

**Quản lý:**
- Xem danh sách theo nhóm
- Xóa các mục không chính xác (nên làm nếu AI trích xuất sai)

---

## 13. Quản lý Người dùng & Nhóm *(Admin)*

**Truy cập:** Sidebar → **Quản lý người dùng**

### Users:
- Tạo user: nhập email, password, role
- Chỉnh sửa role, kích hoạt/vô hiệu hoá tài khoản
- Đặt lại mật khẩu

### Roles có thể gán:
| Role | Dùng cho |
|---|---|
| `system_admin` | Quản trị viên, toàn quyền |
| `knowledge_architect` | Quản lý kho tri thức, prompt |
| `pm_po` | PM, Product Owner, Team Lead |
| `ba_sa` | Business Analyst, System Analyst |
| `dev_qa` | Developer, QA Engineer |
| `standard` | Người dùng thông thường |

### Groups:
- Tạo nhóm, gán user vào nhóm
- Groups dùng để phân quyền xem AI Task Drafts theo scope

---

## 14. AI Workflows *(PM/PO, BA/SA)*

**Truy cập:** Sidebar → **AI Workflows**

Module đang phát triển — cho phép định nghĩa và chạy workflow tùy chỉnh nhiều bước AI. Chức năng còn hạn chế.

---

## 15. Những điều cần biết

### Khi nào hệ thống hữu ích:
- Tìm kiếm nhanh trong tài liệu đông đúc, khó nhớ
- Tạo bản nháp đầu tiên để tiết kiệm thời gian soạn thảo
- Tra cứu quyết định kỹ thuật hoặc nghiệp vụ đã ghi chép

### Khi nào KHÔNG nên tin hoàn toàn:
- Tài liệu đầu vào lỗi thời hoặc chưa đầy đủ
- Câu hỏi yêu cầu suy luận phức tạp ngoài phạm vi tài liệu
- Tài liệu đầu ra dùng cho mục đích chính thức, contract, hay quyết định kinh doanh quan trọng

### Báo lỗi:
1. Chụp màn hình vấn đề
2. Ghi lại câu hỏi / bước thực hiện
3. Báo admin hoặc team dev kèm thông tin trên

---

## 16. FAQ

**Q: Chat trả lời sai hoặc không liên quan?**  
A: Khả năng cao tài liệu chưa nạp hoặc đã lỗi thời. Báo admin để sync lại tài liệu.

**Q: Draft đang "processing" mãi không xong?**  
A: Job timeout tối đa 25 phút. Nếu quá 25 phút mà vẫn processing → báo admin. Có thể Ollama bị quá tải hoặc down.

**Q: Tôi không thấy module X trong sidebar?**  
A: Role của bạn không có quyền. Liên hệ admin để điều chỉnh.

**Q: Dữ liệu tôi nhập có gửi ra internet không?**  
A: Không. LLM và embedding model chạy local qua Ollama, DB lưu local. Trừ khi Connector Jira/Confluence/Slack được bật để kéo dữ liệu về — nhưng chiều ngược lại (dữ liệu ra ngoài) không xảy ra.

**Q: Tôi có thể tạo nhiều draft cùng lúc không?**  
A: Có. Các jobs vào hàng đợi `arq:ai` và xử lý theo thứ tự. Nhiều job cùng lúc cần nhiều tài nguyên Ollama hơn.

**Q: Chat history có lưu lại không?**  
A: Có, lưu trong DB PostgreSQL. Xem lại trong tab Chat bên trái.

**Q: Tại sao kết quả Chat hôm nay khác hôm qua cùng câu hỏi?**  
A: Semantic cache có TTL. Nếu cache hết hạn và tài liệu mới được nạp thêm, LLM có thể tổng hợp khác. Đây là hành vi bình thường.
