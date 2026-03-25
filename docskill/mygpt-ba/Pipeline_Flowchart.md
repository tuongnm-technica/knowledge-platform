# Sơ đồ Luồng Nền Tảng (Pipeline Flowchart)

Tài liệu này mô tả kiến trúc luân chuyển dữ liệu đa chiều của **MyGPT BA Suite**, bao gồm luồng thực thi chính (Happy Path), chốt chặn phê duyệt của con người (Human-in-the-loop), và vòng lặp phản hồi (Reject Routing).

## 1. Sơ đồ Kiến trúc Tổng thể (Mermaid Diagram)

*Hỗ trợ render trực tiếp trên GitHub, GitLab, Notion, Confluence hoặc các trình biên dịch Markdown có hỗ trợ Mermaid.*

```mermaid
graph TD
    %% Styles
    classDef human fill:#ffebee,stroke:#d81b60,stroke-width:2px,color:#000;
    classDef agent fill:#e3f2fd,stroke:#1e88e5,stroke-width:2px,color:#000;
    classDef db fill:#e8f5e9,stroke:#43a047,stroke-width:2px,color:#000;
    classDef external fill:#fff3e0,stroke:#fbc02d,stroke-width:2px,stroke-dasharray: 5 5,color:#000;

    %% Input Group
    Input[Raw Input: Note, Email, Slack, CR]:::human --> G1

    %% Phase 1: Requirement
    subgraph Phase 1: Thu thập & Đánh giá Yêu cầu
        G1[GPT-1: Requirement Analyst]:::agent
        DB1[(Draft DB: Chờ duyệt)]:::db
        H1{BA/PO Duyệt}:::human
        G2[GPT-2: Architect Reviewer]:::agent
        Reject1[❌ Reject JSON]:::agent
        
        G1 -->|Validate Lớp 3| DB1
        DB1 --> H1
        H1 -->|Approve| G2
        H1 -->|Edit/Feedback| G1
        G2 -->|Phát hiện mâu thuẫn| Reject1
        Reject1 -.->|Feedback Loop| G1
    end

    %% Phase 2: Design
    subgraph Phase 2: Thiết kế & Tài liệu
        G3[GPT-3: Solution Designer]:::agent
        G4[GPT-4: Document Writer]:::agent
        DB2[(Draft DB: Chờ duyệt)]:::db
        H2{SA/PM Duyệt}:::human

        G2 -->|Valid JSON| G3
        G3 --> G4
        G4 -->|Output: SRS, BRD| DB2
        DB2 --> H2
        H2 -->|Edit/Feedback| G4
    end

    %% Phase 3: Execution
    subgraph Phase 3: Phân rã & Thực thi
        H2 -->|Approve| G5[GPT-5: User Story Writer]:::agent
        Jira((Jira / Task Manager)):::external
        G6[GPT-6: FE Technical Spec]:::agent
        G7[GPT-7: QA Reviewer]:::agent
        Reject2[❌ Reject JSON]:::agent

        G5 -->|API Push Tasks| Jira
        G5 --> G6
        G6 --> G7
        G7 -->|Thiếu AC Testable| Reject2
        Reject2 -.->|Feedback Loop| G5
    end
```

## 2. Diễn giải các luồng cơ bản

### 2.1. Luồng chạy chính (Happy Path)
Tài liệu sẽ di chuyển từ `GPT-1` đến `GPT-9` theo một Pipeline ID duy nhất (ví dụ `intake_id`). JSON Output của tác tử trước đóng vai trò là Context Input hoàn hảo cho tác tử sau.

### 2.2. Human-in-the-loop (Chốt chặn duyệt)
Để chống "Ảo tưởng tự động hóa", hệ thống không chạy một mạch từ GPT-1 xuống GPT-9.
- Các bản nháp được lưu xuống **Draft DB**.
- Tạm dừng Pipeline cho đến khi con người (BA, PO, SA) lên UI để **Approve** (phê duyệt) hoặc **Sửa đổi** (Edit).

### 2.3. Vòng lặp phản hồi (Reject Routing)
Các tác tử đóng vai trò Reviewer (`GPT-2`, `GPT-7`) có khả năng tự suy luận logic. Nếu phát hiện đầu vào bị thiếu, sai hoặc mâu thuẫn với Business Rules, chúng trả về JSON với trạng thái `reject`, thay vì cố gắng sinh tài liệu rác. Dữ liệu này được gửi ngược về Agent làm lỗi để sửa lại hoặc yêu cầu con người can thiệp bổ sung thông tin.