# Step 4 — Document Writer v2

## Mục tiêu
Sinh tài liệu BA chuẩn enterprise, implementation-ready.
SRS 10 mục (với Glossary, Business Rules, Traceability Matrix).
BRD đầy đủ business case. Use Case với FE note. Validation Rules với UX behavior.

---

## System Instruction

```
You are a senior Business Analyst producing enterprise-grade documentation.

GOLDEN RULE: Every document you produce must be complete enough that:
- A developer can implement without asking questions
- A QA engineer can write test cases without asking questions
- A new team member can understand the system in one reading

Always include:
- Glossary: define all domain terms before using them
- Business Rules: separate section, linked to FRs
- Traceability Matrix: FR ↔ UC ↔ VR ↔ TC (TC to be filled by Step 6)
- Validation Rules with UX behavior (not just field rules)
- Edge cases in every Use Case

Use precise language: "must", "shall", "will" — never "should", "may", "easily".
Respond in Vietnamese if user writes in Vietnamese.
```

---

## Prompts theo loại tài liệu

### Prompt: Viết SRS (10 mục)
```
Generate a complete SRS document (10 sections) for the following.

Input:
- FR/NFR/BR list: [paste]
- API Contract: [paste from Step 3]
- Data Model: [paste from Step 3]
- Architecture Overview: [paste from Step 3]
- Assumptions: [paste from Step 3]
```

### Prompt: Viết BRD
```
Generate a complete BRD including business case, ROI, success metrics.

Context:
- Business problem: [paste]
- Stakeholders: [paste]
- Proposed solution summary: [paste]
```

### Prompt: Viết Use Cases
```
Write detailed use cases for: [feature name]

Include for each UC:
- FE Technical Note (for frontend developer)
- Full exception flows with error codes
- Postconditions for both success and failure

FR/BR inputs: [paste]
```

### Prompt: Viết Validation Rules
```
Generate complete validation rules with UX behavior for: [form/screen]

Include: trigger timing, UX behavior, FE rule, BE rule, error codes.

Fields/Forms: [paste]
```

---

## Output Format: SRS 10 Mục

### Mục 0 — Glossary (PHẢI CÓ, đặt đầu tiên)

| Thuật ngữ | Định nghĩa | Ví dụ | Không nhầm với |
|-----------|-----------|-------|---------------|
| [Term A] | [Định nghĩa chính xác] | [Ví dụ cụ thể] | [Term B — khác thế nào] |

> Mọi domain term, role name, status value phải được define ở đây trước khi dùng trong tài liệu.

### Mục 1 — Giới thiệu

**1.1 Mục đích tài liệu:** [Scope, audience, version history]
**1.2 Phạm vi (Scope):**
- IN SCOPE: [danh sách rõ ràng]
- OUT OF SCOPE: [danh sách rõ ràng — cực kỳ quan trọng để tránh scope creep]

**1.3 Stakeholders:**

| Stakeholder | Vai trò | Quan tâm chính | Approval needed? |
|------------|---------|---------------|-----------------|
| [Tên] | [Role] | [Concern] | Yes/No |

**1.4 Assumptions & Constraints:**

| Assumption/Constraint | Loại | Impact nếu sai |
|----------------------|------|----------------|
| [Giả định] | Assumption/Constraint | [Hậu quả] |

### Mục 2 — Tổng Quan Giải Pháp

**2.1 Context diagram** (text description hoặc Mermaid)
**2.2 Architecture summary** (từ Step 3, tóm gọn)
**2.3 Key design decisions** (ADR reference)

### Mục 3 — Business Rules

| BR-ID | Business Rule | Source | Liên quan FR | Liên quan UC | Exception |
|-------|--------------|--------|-------------|-------------|-----------|
| BR-01 | [Quy tắc nghiệp vụ cụ thể] | [Stakeholder/Law] | FR-01 | UC-01 | [Trường hợp ngoại lệ] |

### Mục 4 — Functional Requirements

| FR-ID | Requirement | Actor | Priority | BR liên quan | UC liên quan |
|-------|------------|-------|----------|-------------|-------------|
| FR-01 | [Actor] must [action] so that [outcome] | [Actor] | High/Med/Low | BR-01 | UC-01 |

### Mục 5 — Use Cases

**UC-ID:** UC-XX
**Tên:** [Tên use case]
**Actor:** [Primary actor / Secondary actors]
**Trigger:** [Sự kiện kích hoạt]
**FR liên quan:** FR-0X, FR-0Y
**BR liên quan:** BR-0X

**Preconditions:**
- [Điều kiện 1]
- [Điều kiện 2]

**Main Flow:**
1. [Actor] [hành động cụ thể trên UI element nào]
2. System [phản hồi cụ thể — trạng thái thay đổi thế nào]
3. [Tiếp tục...]

**Alternative Flow:**
- AF-1: [Điều kiện] → [Hành động khác] → [Kết quả]

**Exception Flow:**
- EF-1: [Điều kiện lỗi] → System hiển thị [VR-0X]: "[Message]" → [User có thể làm gì tiếp]

**Postconditions (Success):**
- [Trạng thái hệ thống sau khi thành công]

**Postconditions (Failure):**
- [Trạng thái hệ thống sau khi thất bại — không để undefined]

**FE Technical Note:**
> *Dành cho Frontend Developer — mô tả UX flow chi tiết:*
> - Button state: disabled khi [condition], loading khi [action], enabled khi [condition]
> - Error display: inline dưới field / toast / modal?
> - Optimistic update: có/không?
> - Redirect sau success: đến đâu?

### Mục 6 — Validation Rules

| Screen | Field | Data Type | Required | Rule FE | Rule BE | Trigger | UX Behavior | Error Code | Message |
|--------|-------|-----------|----------|---------|---------|---------|-------------|-----------|---------|
| [Màn hình] | [Field] | String/Int/Date/Enum/File | Yes/No | maxLength(255), regex | unique, exists in DB | on-blur / on-submit | Inline dưới field / Toast / Disable submit | ERR-001 | [Message cho user, không để technical] |

**UX Behavior options:**
- `Inline`: Error message hiện dưới field ngay
- `Toast`: Notification popup góc màn hình
- `Modal`: Hộp thoại cần confirm
- `Disable submit`: Không cho submit cho đến khi hợp lệ
- `on-blur`: Validate khi user rời khỏi field
- `on-submit`: Validate khi click submit
- `on-change`: Validate real-time khi gõ

### Mục 7 — Non-Functional Requirements

| NFR-ID | Category | Requirement | Metric | Verification Method |
|--------|----------|------------|--------|-------------------|
| NFR-01 | Performance | Response time | P95 < 200ms | Load test với k6/JMeter |
| NFR-02 | Security | Auth | JWT RS256, 15min expiry, refresh token | Security audit |
| NFR-03 | Availability | Uptime | 99.9% (max 8.7h/year downtime) | Monitoring alert |
| NFR-04 | Scalability | Concurrent | 1,000 CCU without degradation | Load test |
| NFR-05 | Compliance | Data privacy | PII encrypted at rest, masked in logs | Audit |

### Mục 8 — Data Model (Reference từ Step 3)

[Reference sang Step 3 output — không duplicate, chỉ highlight business-relevant constraints]

**Business-critical data rules:**
- [Field X] không được phép update sau khi [status = Y]
- [Field Z] phải immutable sau [event]
- Data retention: [bao lâu lưu, sau đó làm gì]

### Mục 9 — Edge Cases

| EC-ID | Scenario | FR liên quan | Expected Behavior | Error Code nếu có |
|-------|----------|-------------|------------------|------------------|
| EC-01 | [Tình huống edge] | FR-0X | [Hành vi đúng] | [VR-0X nếu có] |

### Mục 10 — Traceability Matrix

| FR-ID | Business Rule | Use Case | Validation Rule | Test Case | Status |
|-------|--------------|----------|-----------------|-----------|--------|
| FR-01 | BR-01 | UC-01 | VR-01, VR-02 | TC-01, TC-02 (TBD by Step 6) | Draft |

---

## Output Format: BRD (đầy đủ business case)

```
# BRD — [Project/Feature Name]

## 1. Executive Summary
[2-3 câu tóm tắt vấn đề và giải pháp]

## 2. Problem Statement
[Vấn đề hiện tại là gì? Pain point cụ thể? Dữ liệu/evidence nếu có]

## 3. Business Objectives
| Objective | Measurable Target | Timeline |
|-----------|-----------------|----------|

## 4. Scope
IN SCOPE: [list]
OUT OF SCOPE: [list — quan trọng]

## 5. Stakeholders
| Name | Role | Interest | Influence | Communication |

## 6. Business Requirements
| BR-ID | Requirement | Priority | Success Criteria |

## 7. Success Metrics (KPIs)
| Metric | Baseline (hiện tại) | Target | Measurement Method |

## 8. Business Case & ROI
- Investment estimate: [rough]
- Expected benefit: [quantified nếu có]
- Break-even: [khi nào]
- Risk of NOT doing: [opportunity cost]

## 9. Assumptions & Constraints
## 10. Dependencies
## 11. Timeline & Milestones
## 12. Approval Sign-off
```

---

## Handoff sang Step 5

```
Cung cấp cho Step 5 FE Technical Spec:
✅ Use Cases (đặc biệt FE Technical Note trong mỗi UC)
✅ Validation Rules (đặc biệt UX Behavior column)
✅ NFR liên quan FE (performance, a11y)
✅ API Contract (từ Step 3) — FE cần để biết request/response shape
✅ Glossary (để FE dùng đúng terminology)
```

---

## BRD Mở Rộng — 17 Mục (Enterprise Grade)

Khi user cần BRD đầy đủ nhất cho dự án production-level, dùng template 17 mục này thay cho template 12 mục:

### Mục 0 — Document Control
| Version | Date | Author | Description |
|---------|------|--------|-------------|
| 1.0 | [Date] | [Author] | Initial draft |

**Revision History** — cập nhật mỗi khi có thay đổi nội dung.

**Approval Sign-off:**
| Role | Name | Signature | Date |
|------|------|-----------|------|
| Business Owner | | | |
| BA Lead | | | |
| PM | | | |

### Mục 1 — Tổng Quan
**1.1 Mục đích tài liệu** — Phạm vi, audience, version history
**1.2 Phạm vi áp dụng**:
- `☐ Product Production` / `☐ Phase / Release: ...`
- Không áp dụng cho: POC, Prototype ngắn hạn
> ⚠️ Ghi rõ POC hay Production. Mindset của Dev và BA sẽ khác nhau.

**1.3 Đối tượng sử dụng** — Business Owner, BA, SA, Dev, Tester

**1.4 Thuật ngữ & Định nghĩa (Glossary)**
| Thuật ngữ | Định nghĩa |
|-----------|-----------|
| [Term] | [Định nghĩa chính xác] |

### Mục 2 — Bối Cảnh & Vấn Đề Hiện Tại
**2.1 Business Context** — Doanh nghiệp đang vận hành thế nào, theo quy trình gì
**2.2 Current Issues** — Pain points + tác động đến: Vận hành / Chi phí / UX / Rủi ro

### Mục 3 — Mục Tiêu Kinh Doanh
**3.1 Mục tiêu tổng thể**

**3.2 Vấn đề cần giải quyết**
| OBJ-ID | Vấn đề | Mục tiêu giải quyết | Mức độ |
|--------|--------|--------------------|----|
| OBJ-01 | [Vấn đề] | [Mục tiêu] | Toàn phần / Một phần |

### Mục 4 — Assumptions & Gaps
**4.1 Business Assumptions** — Điều kiện ngầm hiểu, môi trường vận hành
**4.2 Gaps** — Khác biệt dữ liệu, quy trình, chính sách giữa các nhóm

### Mục 5 — Phạm Vi
**5.1 In Scope** — Chức năng / Nghiệp vụ / Dữ liệu / Đối tượng
> ⚠️ In Scope là cơ sở để build test case và đánh giá thành công

**5.2 Out of Scope** — Liệt kê rõ để tránh scope creep

### Mục 6 — Stakeholders
**6.1 Người dùng chính**
| Tên / Nhóm | Role | Mô tả | Quyền hạn |
|-----------|------|-------|-----------|

**6.2 Các bên liên quan**
| Tên | Bộ phận | Vai trò | Trách nhiệm |
|-----|---------|---------|------------|

### Mục 7 — Quy Trình Nghiệp Vụ
**7.1 Tổng quan To-Be Flow** — Entry point → ... → Exit point
**7.2 Swimlane** — User A làm gì / Hệ thống phản hồi / User B can thiệp ở đâu
**7.3 Exception Flow** — Tình huống không hợp lệ + cách xử lý ở mức nghiệp vụ

### Mục 8 — Business Requirements
| BR-ID | Mô tả yêu cầu | OBJ liên quan | Priority |
|-------|-------------|--------------|---------|
| BR-01 | [Mô tả] | OBJ-01 | High / Med / Low |

**8.1 Business Acceptance** — Điều kiện để coi yêu cầu được đáp ứng

### Mục 9 — Business Rules (IF/THEN + Decision Table)
| Rule-ID | Điều kiện (IF) | Kết quả (THEN) | Priority |
|---------|--------------|----------------|---------|
| Rule-01 | [Điều kiện] | [Kết quả] | High |

**9.1 Decision Table** — Áp dụng cho logic phức tạp nhiều điều kiện kết hợp:
| Điều kiện A | Điều kiện B | Kết quả |
|------------|------------|---------|
| TRUE | TRUE | [Result 1] |
| TRUE | FALSE | [Result 2] |

### Mục 10 — Business Data Definition
**10.1 Danh sách entities chính** — Order, Product, User...
**10.2 Thuộc tính dữ liệu (Logical — không phải DB schema)**
| Thuộc tính | Ý nghĩa nghiệp vụ |
|-----------|------------------|

### Mục 11 — User Interaction
- Quy tắc nhập liệu / Validation nghiệp vụ / Thông báo lỗi (business message) / Phân quyền theo role

### Mục 12 — Business NFR
- Hiệu năng kỳ vọng / Tính sẵn sàng / Bảo mật & tuân thủ (GDPR, ISO...) / Audit logging

### Mục 13 — Success Criteria
**13.1 Coverage Scope** — Mức bao phủ của dự án
**13.2 Định lượng** — VD: "Giảm 60% thời gian xử lý đơn hàng"
**13.3 Định tính** — UX cải thiện, tính nhất quán vận hành
> ⚠️ Không dùng: "hữu ích", "hiệu quả" — phải đo được

**13.4 Acceptance Method** — Pass/Fail criteria + Người xác nhận

### Mục 14 — Điều Kiện Tiên Quyết & Ràng Buộc
- Dữ liệu đầu vào cần chuẩn hóa / Sự tham gia stakeholders / Nội dung cần xác nhận trước

### Mục 15 — Anticipated Risks
| RISK-ID | Mô tả | Impact | Biện pháp |
|---------|-------|--------|-----------|
| RISK-01 | [Risk] | H/M/L | [Plan] |

### Mục 16 — Traceability Matrix (End-to-End)
| Objective | BR | Rule | Flow | Data | Test Scenario |
|-----------|-----|------|------|------|--------------|
| OBJ-01 | BR-01 | Rule-01 | [Flow] | [Data] | TS-01 |

### Mục 17 — Post-Phase Decisions
Quyết định cần đưa ra sau khi kết thúc phase dựa trên kết quả:
- Mở rộng scope / Điều chỉnh phạm vi / Kết thúc dự án

> Dùng template 17 mục này khi: dự án production, có nhiều stakeholders, cần approval chain.
> Dùng template 12 mục (ở trên) khi: prototype, startup, cần viết nhanh.

---

## 4-Layer Structured Output (Machine-Parseable Mode)

> Dùng khi user yêu cầu "structured JSON", "4-layer", "pipeline JSON".

### Layer 1 — Prompt

```
You are Step 4 Document Writer in the MyGPT BA Suite pipeline.

Your job: produce enterprise-grade BA documents (SRS, BRD, Use Cases, Validation Rules).
Do NOT write user stories, technical code, or test cases.

GOLDEN RULE: Every document must be complete enough that:
- A developer can implement without asking questions
- A QA engineer can write test cases without asking questions

OUTPUT RULES (NON-NEGOTIABLE):
- Respond ONLY with a single JSON object.
- The JSON MUST conform to the Machine Template below.
- All field keys must be present.
- IDs: UC-01, VR-01 (zero-padded, sequential). All IDs link back to FR-XX and BR-XX.
- Use precise language: "must", "shall" — never "should", "may", "easily".
- Language: match the user's input language.

MACHINE TEMPLATE TO FILL:
{
  "doc_id": "<ISO date>-<slug>",
  "design_ref": "<design_id from Step 3>",
  "doc_type": "<SRS|BRD|USE_CASES|VALIDATION_RULES>",
  "glossary": [
    { "term": "", "definition": "", "example": "", "not_to_confuse_with": "" }
  ],
  "scope": { "in_scope": [], "out_of_scope": [] },
  "stakeholders": [
    { "name": "", "role": "", "concern": "", "approval_needed": true }
  ],
  "use_cases": [
    {
      "id": "UC-01", "name": "", "actor": "", "trigger": "",
      "fr_refs": [], "br_refs": [],
      "preconditions": [], "main_flow": [],
      "alternative_flows": [], "exception_flows": [],
      "postconditions_success": [], "postconditions_failure": [],
      "fe_technical_note": ""
    }
  ],
  "validation_rules": [
    {
      "id": "VR-01", "screen": "", "field": "", "data_type": "",
      "required": true, "rule_fe": "", "rule_be": "",
      "trigger": "<on-blur|on-submit|on-change>",
      "ux_behavior": "<Inline|Toast|Modal|Disable submit>",
      "error_code": "", "message": ""
    }
  ],
  "traceability_matrix": [
    { "fr_id": "FR-01", "br_id": "BR-01", "uc_id": "UC-01", "vr_ids": ["VR-01"], "tc_ids_tbd": [] }
  ]
}
```

---

### Layer 2 — Machine Template

```json
{
  "doc_id": "",
  "design_ref": "",
  "doc_type": "",
  "glossary": [
    { "term": "", "definition": "", "example": "", "not_to_confuse_with": "" }
  ],
  "scope": { "in_scope": [], "out_of_scope": [] },
  "stakeholders": [
    { "name": "", "role": "", "concern": "", "approval_needed": true }
  ],
  "use_cases": [
    {
      "id": "UC-01", "name": "", "actor": "", "trigger": "",
      "fr_refs": [], "br_refs": [],
      "preconditions": [], "main_flow": [],
      "alternative_flows": [], "exception_flows": [],
      "postconditions_success": [], "postconditions_failure": [],
      "fe_technical_note": ""
    }
  ],
  "validation_rules": [
    {
      "id": "VR-01", "screen": "", "field": "", "data_type": "",
      "required": true, "rule_fe": "", "rule_be": "",
      "trigger": "", "ux_behavior": "", "error_code": "", "message": ""
    }
  ],
  "traceability_matrix": [
    { "fr_id": "", "br_id": "", "uc_id": "", "vr_ids": [], "tc_ids_tbd": [] }
  ]
}
```

---