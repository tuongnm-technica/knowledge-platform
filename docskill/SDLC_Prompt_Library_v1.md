# SDLC Prompt Library v1.0

## Thư viện Prompt cho Chu trình Phát triển Phần mềm

| Metadata | |
|---|---|
| **Version** | 1.0 |
| **Date** | 09/03/2026 |
| **Workstream** | 3 — AI Strategy Roadmap |
| **Tài sản** | Tài sản 1 (phần phụ): AI-Prompt-Patterns-v1.md |
| **Input** | SDLC_AI_Integration_Roadmap_v1.docx, Gap Analysis v1.0, Templates Pack v7.1 |
| **Owner** | AI Pilot Lead + Role Leads (BA, SA, QA, PM, DevOps) |
| **Liên kết** | SDLC_AI_Playbook_v1.docx (Ch.4 Tool Selection, Ch.5 Review Gates) |

---

## Mục lục (Table of Contents)

- [Hướng dẫn Sử dụng](#hướng-dẫn-sử-dụng)
- [BA Prompts](#ba-prompts)
  - [BA-01: Tạo BRD Draft](#ba-01-tạo-brd-draft)
  - [BA-02: Review SRS Quality](#ba-02-review-srs-quality)
  - [BA-03: Sinh Acceptance Criteria (Gherkin)](#ba-03-sinh-acceptance-criteria-gherkin)
  - [BA-04: Gap Analysis Requirements](#ba-04-gap-analysis-requirements)
- [SA Prompts](#sa-prompts)
  - [SA-01: Review HLD Consistency](#sa-01-review-hld-consistency)
  - [SA-02: Sinh ADR Draft](#sa-02-sinh-adr-draft)
  - [SA-03: NFR Checklist theo ISO 25010](#sa-03-nfr-checklist-theo-iso-25010)
  - [SA-04: API Spec Draft (OpenAPI)](#sa-04-api-spec-draft-openapi)
- [QA Prompts](#qa-prompts)
  - [QA-01: Sinh Test Cases từ AC](#qa-01-sinh-test-cases-từ-ac)
  - [QA-02: Review Test Plan](#qa-02-review-test-plan)
  - [QA-03: DoD Compliance Check](#qa-03-dod-compliance-check)
- [PM Prompts](#pm-prompts)
  - [PM-01: Weekly Status Report Draft](#pm-01-weekly-status-report-draft)
  - [PM-02: Risk Assessment](#pm-02-risk-assessment)
  - [PM-03: Stakeholder Communication](#pm-03-stakeholder-communication)
- [DevOps Prompts](#devops-prompts)
  - [DevOps-01: Runbook Draft](#devops-01-runbook-draft)
  - [DevOps-02: Incident Postmortem](#devops-02-incident-postmortem)
  - [DevOps-03: Release Notes](#devops-03-release-notes)

---

## Hướng dẫn Sử dụng

### Cấu trúc mỗi Prompt Pattern

Mỗi pattern gồm 6 phần:

1. **Tên + Mục đích**: Pattern ID, tên, mục tiêu sử dụng.
2. **Input cần chuẩn bị**: Dữ liệu phải có TRƯỚC khi chạy prompt. Thiếu input = output kém.
3. **Prompt Template**: Copy-paste trực tiếp. Thay `[placeholder]` bằng data thực.
4. **Good Example**: Output mẫu đạt chuẩn (trích đoạn).
5. **Anti-pattern**: Output xấu + lý do xấu. Tránh lặp lại.
6. **Review Checklist**: Kiểm tra SAU KHI AI tạo output, TRƯỚC KHI sử dụng.

### Quy tắc chung

- LUÔN cung cấp context đầy đủ (domain, template structure, ví dụ).
- LUÔN review output theo checklist trước khi dùng (xem Playbook Ch.5).
- KHÔNG bao giờ trust AI 100% cho số liệu, tên riêng, ngày tháng.
- Prompt càng cụ thể, output càng tốt. "Tạo BRD" < "Tạo BRD cho module thanh toán e-commerce B2C, target user 18-35."
- [C] Thực hành phổ biến. Prompt engineering best practices.

### Data Classification Reminder

Trước khi paste BẤT KỲ dữ liệu nào vào AI tool, kiểm tra mức data classification (xem Playbook Ch.3):
- **Public**: Dùng bất kỳ tool nào.
- **Internal**: Chỉ Business/Team/Enterprise tier.
- **Confidential**: Chỉ Enterprise tier có DLP.
- **Restricted**: CẤM tuyệt đối.

---

## BA Prompts

### BA-01: Tạo BRD Draft

| | |
|---|---|
| **Pattern ID** | BA-01 |
| **Tên** | BRD-Draft |
| **Mục đích** | Tạo Business Requirements Document draft từ meeting notes và project context |
| **Vai trò** | BA (Author), PM (Reviewer) |
| **Evidence Level** | [Proven] — P1.2 trong Roadmap v1 |
| **Tool khuyến nghị** | Claude Projects / ChatGPT Business (WebUI) |

#### Input cần chuẩn bị

1. Meeting notes / stakeholder interview summary (đã tổng hợp)
2. Project charter hoặc project brief (nếu có)
3. BRD template structure từ Templates Pack v7.1 (sheet: BRD)
4. Domain glossary (danh sách thuật ngữ chuyên ngành)
5. Ví dụ BRD cũ của công ty (nếu có) — để AI bắt chước tone/format

#### Prompt Template

```
Bạn là Business Analyst có 10 năm kinh nghiệm. Tạo BRD draft cho dự án theo thông tin dưới đây.

## Project Context
[Paste project charter/brief: tên dự án, mục tiêu kinh doanh, phạm vi cao, stakeholders chính, timeline dự kiến]

## Meeting Notes / Interview Summary
[Paste meeting notes đã tổng hợp]

## BRD Template Structure (bắt buộc tuân theo)
1. Document Control (version, author, reviewer, approval)
2. Executive Summary
3. Business Objectives & Success Metrics
4. Scope (In-Scope / Out-of-Scope)
5. Stakeholder Analysis (stakeholder, role, interest, influence)
6. Business Requirements (ID: BRQ-xxx, description, priority MoSCoW, source, acceptance criteria)
7. Business Rules
8. Assumptions & Constraints
9. Dependencies
10. Glossary

## Domain Glossary
[Paste thuật ngữ chuyên ngành nếu có]

## Output Requirements
- Viết bilingual: Vietnamese chính + English terminology trong ngoặc
- Mỗi requirement có ID format BRQ-001, BRQ-002...
- Priority dùng MoSCoW (Must/Should/Could/Won't)
- Acceptance Criteria dạng Gherkin (Given/When/Then) cho mỗi BRQ
- Đánh dấu [NEEDS HUMAN] cho sections cần business decision mà AI không đủ context
- Đánh dấu [VERIFY] cho mọi số liệu, tên riêng, ngày tháng cụ thể

Tạo BRD draft. Ưu tiên completeness (đủ sections) hơn depth (sâu từng section).
```

#### Good Example (trích đoạn)

```
## 3. Business Objectives & Success Metrics

| # | Mục tiêu Kinh doanh (Business Objective) | Metric Đo lường | Target | Timeline |
|---|---|---|---|---|
| BO-1 | Giảm thời gian xử lý đơn hàng (order processing time) | Avg processing time | Từ 48h xuống 12h [VERIFY] | Q3 2026 |
| BO-2 | Tăng tỷ lệ khách hàng quay lại (retention rate) | Monthly retention | +15% so với baseline [VERIFY] | Q4 2026 |

## 6. Business Requirements

| ID | Mô tả (Description) | Priority | Source | Acceptance Criteria |
|---|---|---|---|---|
| BRQ-001 | Hệ thống phải cho phép khách hàng đặt hàng online qua mobile app và web portal | Must | Stakeholder interview 15/02 | Given khách hàng đã đăng nhập, When chọn sản phẩm và nhấn "Đặt hàng", Then đơn hàng được tạo với trạng thái "Pending" và gửi confirmation email trong 30s |
| BRQ-002 | [NEEDS HUMAN] Hệ thống phải tích hợp với cổng thanh toán hiện tại (payment gateway) | Must | Project Charter | Given đơn hàng có tổng giá trị > 0, When khách chọn phương thức thanh toán, Then redirect sang payment gateway và nhận callback trong [VERIFY] giây |
```

#### Anti-pattern (BAD — tránh)

```
## Business Requirements
1. Hệ thống phải nhanh
2. Hệ thống phải bảo mật
3. Hệ thống phải dễ dùng
```

**Tại sao xấu:**
- Không có ID → không trace được trong RTM.
- Không có priority → không biết làm gì trước.
- Quá chung chung ("nhanh", "bảo mật") → không test được, không verify được.
- Không có Acceptance Criteria → không biết khi nào "done".
- Thiếu source → không biết requirement từ đâu, ai yêu cầu.
- Không đánh dấu [NEEDS HUMAN] → người đọc tưởng AI đã đủ context.

#### Review Checklist (sau khi AI tạo output)

- [ ] RC1 — Factuality: Số liệu, tên stakeholder, ngày tháng đúng không? (đối chiếu meeting notes)
- [ ] RC2 — Completeness: Có đủ 10 sections theo template không?
- [ ] RC3 — Consistency: Business objectives align với requirements không? Scope vs requirements khớp không?
- [ ] RC5 — Data Sensitivity: Có PII/confidential info lọt vào không?
- [ ] RC6 — Actionability: SA/Dev đọc BRD này có hiểu scope và requirements không?
- [ ] BRD-specific: Mọi BRQ có ID, priority, source, AC không?
- [ ] BRD-specific: [NEEDS HUMAN] sections đã được business owner review chưa?
- [ ] BRD-specific: [VERIFY] items đã được đối chiếu với nguồn gốc chưa?

---

### BA-02: Review SRS Quality

| | |
|---|---|
| **Pattern ID** | BA-02 |
| **Tên** | SRS-Quality-Review |
| **Mục đích** | Kiểm tra chất lượng SRS theo ISO/IEC/IEEE 29148:2018 characteristics |
| **Vai trò** | BA/SA (Author), BA Lead (Reviewer) |
| **Evidence Level** | [Emerging] — P2.1 trong Roadmap v1 |
| **Tool khuyến nghị** | Claude Projects (WebUI) — cần long context |

#### Input cần chuẩn bị

1. SRS document cần review (full text)
2. BRD tương ứng (để cross-check alignment)
3. ISO/IEC/IEEE 29148:2018 quality characteristics checklist (optional — prompt đã nhúng)

#### Prompt Template

```
Bạn là BA Lead với chuyên môn requirements engineering theo ISO/IEC/IEEE 29148:2018. Review SRS dưới đây và đánh giá theo 8 tiêu chí chất lượng requirements.

## SRS Document
[Paste toàn bộ SRS]

## BRD Reference (để cross-check)
[Paste BRD sections liên quan, đặc biệt Business Requirements và Scope]

## Review theo 8 tiêu chí (ISO/IEC/IEEE 29148:2018 Characteristics)
Với MỖI requirement trong SRS, đánh giá:
1. **Necessary** (Cần thiết): Requirement này có truy ngược được về business need không?
2. **Appropriate** (Phù hợp): Mức abstraction đúng cho SRS không? (không quá high-level, không quá implementation)
3. **Unambiguous** (Rõ ràng): Chỉ có 1 cách hiểu duy nhất không?
4. **Complete** (Đầy đủ): Có đủ thông tin để implement + test không?
5. **Singular** (Đơn nhất): Mỗi requirement chỉ nói 1 điều?
6. **Feasible** (Khả thi): Có thể implement được với technology hiện tại không?
7. **Verifiable** (Kiểm chứng được): Có thể viết test case cho requirement này không?
8. **Traceable** (Truy vết được): Link được về BRD requirement gốc không?

## Output Format
Tạo bảng review:
| REQ ID | Tiêu chí FAIL | Mô tả vấn đề | Gợi ý sửa | Severity (High/Medium/Low) |

Sau bảng, tóm tắt:
- Tổng requirements reviewed
- Số requirements PASS tất cả 8 tiêu chí
- Top 3 vấn đề phổ biến nhất
- Khuyến nghị ưu tiên fix

Đánh dấu [VERIFY] cho mọi nhận định cần BA/SA kiểm tra lại.
```

#### Good Example (trích đoạn)

```
| REQ ID | Tiêu chí FAIL | Mô tả vấn đề | Gợi ý sửa | Severity |
|---|---|---|---|---|
| SRS-005 | Unambiguous, Verifiable | "Hệ thống phải phản hồi nhanh" — không có threshold cụ thể | Sửa: "Response time ≤ 2s cho 95th percentile under normal load (≤500 concurrent users)" | High |
| SRS-012 | Singular | Chứa 2 requirements: "Hệ thống phải gửi email xác nhận VÀ cập nhật inventory" | Tách thành SRS-012a (email) và SRS-012b (inventory) | Medium |
| SRS-018 | Traceable | Không tìm thấy BRQ tương ứng trong BRD | [VERIFY] Kiểm tra: requirement mới từ technical need hay thiếu link? | Medium |

**Tóm tắt:** 35 requirements reviewed. 22 PASS (63%). Top issues: (1) Thiếu measurable thresholds (8 REQs), (2) Compound requirements (4 REQs), (3) Missing traceability (3 REQs).
```

#### Anti-pattern (BAD — tránh)

```
SRS looks good overall. A few minor issues:
- Some requirements could be more specific
- Consider adding more details
- Overall quality is acceptable
```

**Tại sao xấu:**
- Không chỉ ra REQUIREMENT CỤ THỂ nào có vấn đề → không actionable.
- "Could be more specific" — specific về cái gì? Theo tiêu chí nào?
- Không dùng ISO 29148 framework → review không systematic.
- Không severity ranking → không biết fix gì trước.

#### Review Checklist

- [ ] RC1 — AI có đánh giá đúng requirements không? (cross-check 3-5 REQs bằng tay)
- [ ] RC3 — AI findings consistent với BRD cross-check không?
- [ ] RC6 — Gợi ý sửa có cụ thể, actionable không?
- [ ] SA/BA-specific: False positive rate thấp không? (AI flag nhầm <30%)
- [ ] SA/BA-specific: AI có miss issues mà bạn thấy bằng mắt không?

---

### BA-03: Sinh Acceptance Criteria (Gherkin)

| | |
|---|---|
| **Pattern ID** | BA-03 |
| **Tên** | AC-Gherkin-Generate |
| **Mục đích** | Sinh Acceptance Criteria dạng Given/When/Then từ requirements |
| **Vai trò** | BA (Author), QA (Reviewer — verify testability) |
| **Evidence Level** | [Proven] — P1.3, P1.10 trong Roadmap v1 |
| **Tool khuyến nghị** | Claude / ChatGPT (WebUI) |

#### Input cần chuẩn bị

1. Requirements list (BRQ hoặc SRS IDs + descriptions)
2. Domain business rules (ví dụ: "đơn hàng tối thiểu 50.000 VNĐ")
3. User roles / personas (ai dùng feature này)
4. Edge cases đã biết (nếu có)

#### Prompt Template

```
Bạn là BA chuyên viết Acceptance Criteria dạng Gherkin (Given/When/Then) theo chuẩn BDD.

## Requirements
[Paste danh sách requirements cần sinh AC]

## Domain Business Rules
[Paste business rules liên quan: validation rules, giới hạn, điều kiện đặc biệt]

## User Roles
[Liệt kê roles: Admin, Customer, Operator, etc. + quyền chính mỗi role]

## Output Requirements
Với MỖI requirement, tạo:
1. **Scenario chính** (Happy path): Given/When/Then cho flow bình thường
2. **Negative scenarios** (≥2): Given/When/Then cho lỗi phổ biến
3. **Boundary/Edge cases** (≥1): Given/When/Then cho giới hạn (min, max, empty, null)

Format:
```
**REQ-ID: [mô tả ngắn]**

Scenario 1: [tên scenario]
  Given [precondition]
  When [action]
  Then [expected result]

Scenario 2 (Negative): [tên]
  Given [precondition]
  When [invalid action]
  Then [error handling]

Scenario 3 (Boundary): [tên]
  Given [edge condition]
  When [action]
  Then [expected result at boundary]
```

Quy tắc:
- Given/When/Then phải specific, không dùng "hệ thống hoạt động bình thường"
- Dùng data cụ thể trong examples (ví dụ: "amount = 50.000 VNĐ" thay vì "valid amount")
- Mỗi Then chỉ verify 1 outcome
- Đánh dấu [VERIFY] cho business rules AI không chắc chắn
```

#### Good Example (trích đoạn)

```
**BRQ-001: Khách hàng đặt hàng online**

Scenario 1: Đặt hàng thành công (Happy path)
  Given khách hàng "user@email.com" đã đăng nhập
  And giỏ hàng có 2 sản phẩm với tổng giá trị 150.000 VNĐ
  When khách nhấn nút "Đặt hàng"
  Then đơn hàng được tạo với trạng thái "Pending"
  And confirmation email gửi đến "user@email.com" trong 30 giây

Scenario 2 (Negative): Giỏ hàng trống
  Given khách hàng đã đăng nhập
  And giỏ hàng trống (0 sản phẩm)
  When khách nhấn nút "Đặt hàng"
  Then hiển thị thông báo "Giỏ hàng trống, vui lòng thêm sản phẩm"
  And KHÔNG tạo đơn hàng

Scenario 3 (Boundary): Đơn hàng dưới mức tối thiểu
  Given khách hàng đã đăng nhập
  And giỏ hàng có tổng giá trị 49.999 VNĐ [VERIFY: minimum order = 50.000?]
  When khách nhấn nút "Đặt hàng"
  Then hiển thị thông báo "Đơn hàng tối thiểu 50.000 VNĐ"
```

#### Anti-pattern (BAD — tránh)

```
Scenario: Đặt hàng
  Given hệ thống hoạt động bình thường
  When khách hàng đặt hàng
  Then đơn hàng được tạo thành công
```

**Tại sao xấu:**
- "Hệ thống hoạt động bình thường" — không phải precondition, không kiểm tra được.
- "Khách hàng đặt hàng" — quá chung, thiếu action cụ thể.
- Không có negative/boundary scenarios → miss bugs.
- Không có data cụ thể → QA không biết test data nào.
- Chỉ có 1 scenario → chỉ cover happy path.

#### Review Checklist

- [ ] RC1 — Business rules trong AC đúng không? (đối chiếu domain rules)
- [ ] RC2 — Mỗi requirement có ≥3 scenarios (happy + negative + boundary)?
- [ ] RC6 — QA đọc AC này có viết được test case ngay không?
- [ ] AC-specific: Data examples realistic không? (không dùng "test123")
- [ ] AC-specific: [VERIFY] items đã được confirm với business owner chưa?
- [ ] AC-specific: Edge cases có cover giới hạn min/max/empty/null không?

---

### BA-04: Gap Analysis Requirements

| | |
|---|---|
| **Pattern ID** | BA-04 |
| **Tên** | REQ-Gap-Analysis |
| **Mục đích** | Phân tích gap giữa as-is và to-be requirements, hoặc giữa 2 versions |
| **Vai trò** | BA (Author), SA (Reviewer) |
| **Evidence Level** | [Proven] — Cross-cutting analysis task |
| **Tool khuyến nghị** | Claude Projects (WebUI) — cần long context cho 2 documents |

#### Input cần chuẩn bị

1. Document A: As-is requirements (hoặc version cũ)
2. Document B: To-be requirements (hoặc version mới)
3. Scope context: phạm vi comparison (module nào, feature nào)

#### Prompt Template

```
Bạn là BA chuyên phân tích gap requirements. So sánh 2 tài liệu dưới đây và tạo gap analysis report.

## Document A (As-Is / Version cũ)
[Paste Document A]

## Document B (To-Be / Version mới)
[Paste Document B]

## Scope
[Mô tả phạm vi: module nào, feature nào, không so sánh phần nào]

## Output Format
Tạo bảng gap analysis:

| # | Category | Gap Description | Impact (High/Med/Low) | Recommendation | Priority |
|---|---|---|---|---|---|

Categories:
- NEW: Requirements mới trong B mà A không có
- REMOVED: Requirements trong A bị bỏ trong B
- MODIFIED: Requirements thay đổi (nêu rõ thay đổi gì)
- CONFLICT: Requirements mâu thuẫn giữa A và B

Sau bảng:
- Tóm tắt: tổng gaps, phân bổ theo category
- Top 5 gaps có impact cao nhất
- Khuyến nghị: nên xử lý gap nào trước

Đánh dấu [VERIFY] cho impacts mà AI không chắc chắn.
```

#### Good Example (trích đoạn)

```
| # | Category | Gap Description | Impact | Recommendation | Priority |
|---|---|---|---|---|---|
| G-01 | NEW | B thêm BRQ-015: Multi-currency support (USD, EUR, VNĐ) | High — ảnh hưởng payment module, pricing engine, reporting | Cần SRS mới cho currency conversion logic + exchange rate API | P1 |
| G-02 | MODIFIED | BRQ-003: Response time thay đổi từ "< 5s" thành "< 2s" | Medium — cần review architecture (caching, DB optimization) | SA review performance implications | P2 |
| G-03 | REMOVED | A có BRQ-009: SMS notification. B bỏ. | Low [VERIFY] — nếu SMS vẫn cần cho OTP thì phải giữ | Confirm với PO: bỏ SMS notification hay bỏ toàn bộ SMS? | P2 |

**Tóm tắt:** 18 gaps identified. NEW: 7, MODIFIED: 6, REMOVED: 3, CONFLICT: 2.
```

#### Anti-pattern (BAD — tránh)

```
The two documents are largely similar with some differences in requirements coverage. Document B appears to be more comprehensive. Recommend reviewing both documents carefully.
```

**Tại sao xấu:** Không chỉ ra gap CỤ THỂ nào. Không có impact analysis. Không actionable. "Review carefully" — review cái gì?

#### Review Checklist

- [ ] RC1 — Gaps identified chính xác không? (spot-check 5 gaps bằng tay)
- [ ] RC3 — Impact assessment hợp lý không? (cross-check với SA)
- [ ] RC6 — Recommendations actionable không? (có ai, làm gì, priority)
- [ ] Gap-specific: AI có miss gap nào bạn thấy bằng mắt không?
- [ ] Gap-specific: CONFLICT items cần escalate cho PO/PM không?

---

## SA Prompts

### SA-01: Review HLD Consistency

| | |
|---|---|
| **Pattern ID** | SA-01 |
| **Tên** | HLD-Consistency-Review |
| **Mục đích** | Review High-Level Design document — kiểm tra consistency với SRS và NFR |
| **Vai trò** | SA (Author/Reviewer), SA Lead (Approver) |
| **Evidence Level** | [Emerging] — P2.2 trong Roadmap v1 |
| **Tool khuyến nghị** | Claude Projects (WebUI) — cần long context |

#### Input cần chuẩn bị

1. HLD document (full text, bao gồm C4 diagrams nếu có dạng text)
2. SRS document (requirements cần HLD address)
3. NFR list với thresholds (performance, availability, security, etc.)

#### Prompt Template

```
Bạn là Solution Architect Lead. Review HLD dưới đây theo 5 khía cạnh.

## HLD Document
[Paste HLD]

## SRS (requirements phải address)
[Paste SRS hoặc requirements list]

## NFR Thresholds
[Paste NFR list: Performance (response time, throughput), Availability (SLA %), Security (authentication, encryption), Scalability (concurrent users), etc.]

## Review 5 khía cạnh:

### 1. SRS Coverage
- Mỗi functional requirement trong SRS có component/service nào trong HLD address?
- Requirements nào CHƯA được address?

### 2. NFR Compliance (theo ISO/IEC 25010:2023)
- Architecture có đáp ứng từng NFR threshold không?
- Nếu không, trade-off là gì?

### 3. Component Consistency
- Interfaces giữa components có consistent không? (data formats, protocols, error handling)
- Có missing interfaces không?

### 4. Technology Stack Fitness
- Tech stack phù hợp với scale/performance requirements không?
- Có vendor lock-in risk không?
- [VERIFY] phần nào cần SA kiểm chứng với team

### 5. Security Architecture
- Authentication/authorization model đủ không?
- Data flow có sensitive data exposed ở điểm nào không?
- Align với OWASP Top 10:2021 và NIST SP 800-218 v1.1 (SSDF)?

## Output Format
Bảng findings:
| # | Khía cạnh | Finding | Severity | Recommendation |

Tóm tắt: Overall assessment (Approve / Approve with conditions / Reject + rework)
```

#### Good Example (trích đoạn)

```
| # | Khía cạnh | Finding | Severity | Recommendation |
|---|---|---|---|---|
| F-01 | SRS Coverage | SRS-015 (multi-currency) không có component nào address | High | Thêm Currency Service vào Service Layer; define exchange rate data source |
| F-02 | NFR Compliance | NFR-03 (Availability 99.9%) — HLD chỉ có single DB instance, không có failover | High | Thêm DB replication + failover mechanism; estimate RTO/RPO |
| F-03 | Security | API Gateway không mention rate limiting — OWASP A04:2021 Insecure Design risk | Medium | Thêm rate limiting config (suggest: 100 req/min/user) [VERIFY threshold] |

**Overall: Approve with conditions** — fix F-01, F-02 trước khi chuyển LLD.
```

#### Anti-pattern (BAD)

```
The HLD looks well-structured. Architecture appears sound. Minor suggestions: consider adding caching, maybe look into microservices approach.
```

**Tại sao xấu:** Không reference SRS/NFR cụ thể. "Appears sound" — dựa trên tiêu chí nào? "Maybe look into" — không actionable.

#### Review Checklist

- [ ] RC1 — AI findings đúng về tech stack, protocols không? (SA verify)
- [ ] RC3 — SRS coverage check khớp không? (cross-check 5 REQs)
- [ ] RC6 — Recommendations cụ thể, actionable cho SA team?
- [ ] SA-specific: AI có miss architectural issues không? (kinh nghiệm SA)
- [ ] SA-specific: Trade-off analysis hợp lý không?

---

### SA-02: Sinh ADR Draft

| | |
|---|---|
| **Pattern ID** | SA-02 |
| **Tên** | ADR-Draft-Generate |
| **Mục đích** | Tạo Architecture Decision Record draft cho quyết định kiến trúc quan trọng |
| **Vai trò** | SA (Author), SA Lead/CTO (Reviewer — QUYẾT ĐỊNH cuối cùng = HUMAN) |
| **Evidence Level** | [Emerging] — P2.2 trong Roadmap v1. ADR = 🔴 CAO risk template. |
| **Tool khuyến nghị** | Claude Projects (WebUI) |

#### Input cần chuẩn bị

1. Decision context: vấn đề kiến trúc cần giải quyết
2. Options đã xem xét (ít nhất 2-3 options)
3. Constraints: NFR thresholds, budget, timeline, team capability
4. Stakeholders ảnh hưởng bởi quyết định

#### Prompt Template

```
Bạn là Solution Architect. Tạo ADR draft theo Michael Nygard format cho quyết định kiến trúc dưới đây.

## Decision Context
[Mô tả vấn đề cần giải quyết. Ví dụ: "Chọn message broker cho async communication giữa Order Service và Inventory Service"]

## Options đang xem xét
[Liệt kê ≥2 options. Ví dụ:
- Option A: RabbitMQ
- Option B: Apache Kafka
- Option C: AWS SQS]

## Constraints
[NFR thresholds, budget, timeline, team capability, vendor preference]

## Stakeholders
[Ai bị ảnh hưởng: Dev team, Ops, SA, Business]

## ADR Template (bắt buộc tuân theo)
# ADR-[XXX]: [Title]
## Status: [Proposed / Accepted / Deprecated / Superseded]
## Context
## Decision Drivers
## Options Considered
### Option A: [name]
- Pros
- Cons
- Cost estimate
- Team readiness
### Option B: [name]
(tương tự)
## Decision
## Consequences (Positive / Negative / Risks)
## Compliance Notes (ISO 25010:2023 NFR mapping nếu relevant)

## CRITICAL RULE
- AI CHỈ structure trade-offs và phân tích. QUYẾT ĐỊNH cuối cùng = SA Lead/CTO.
- Đánh dấu [DECISION NEEDED] cho phần Decision.
- Đánh dấu [VERIFY] cho mọi cost/performance claims.
```

#### Good Example (trích đoạn)

```
# ADR-003: Message Broker cho Order-Inventory Communication

## Status: Proposed

## Context
Order Service cần gửi async events đến Inventory Service khi đơn hàng được tạo/cập nhật.
Volume dự kiến: ~500 events/phút peak [VERIFY]. Yêu cầu at-least-once delivery.

## Decision Drivers
- DD-1: Throughput ≥ 1.000 msg/s peak (NFR-07)
- DD-2: Message ordering cho cùng order_id (business requirement)
- DD-3: Team chưa có kinh nghiệm Kafka (constraint)
- DD-4: Budget ≤ $500/tháng cho messaging infra [VERIFY]

## Options Considered
### Option A: RabbitMQ
- Pros: Team đã dùng 2 năm; mature routing; plugin ecosystem
- Cons: Scaling beyond 10K msg/s phức tạp; không có native log compaction
- Cost: ~$200/tháng (2 nodes HA) [VERIFY]
- Team readiness: Cao (existing expertise)

### Option B: Apache Kafka
- Pros: Throughput cao; message ordering per partition; event replay
- Cons: Ops complexity cao; team cần 2-4 tuần ramp-up [VERIFY]; overkill cho volume hiện tại
- Cost: ~$400/tháng (3 brokers minimum) [VERIFY]
- Team readiness: Thấp (chưa production experience)

## Decision
[DECISION NEEDED — SA Lead/CTO quyết định dựa trên trade-offs trên]

## Consequences
Nếu chọn Option A (RabbitMQ):
- Positive: Nhanh implement (1-2 sprint); team confident
- Negative: Cần migrate nếu volume vượt 10K msg/s trong tương lai
- Risk: Migration cost nếu business grow nhanh hơn dự kiến
```

#### Anti-pattern (BAD)

```
## Decision
We should use Kafka because it's the industry standard and more scalable.
```

**Tại sao xấu:** AI QUYẾT ĐỊNH thay human. Không nêu trade-offs. "Industry standard" không phải lý do đủ. Không xem xét team capability, cost, timeline.

#### Review Checklist

- [ ] RC1 — Cost estimates, performance numbers đúng không? [VERIFY all]
- [ ] RC2 — Có đủ ≥2 options với pros/cons/cost/team readiness không?
- [ ] RC5 — Có leak sensitive info (pricing, infra details) không?
- [ ] ADR-specific: Decision section có [DECISION NEEDED] không? (AI KHÔNG được quyết)
- [ ] ADR-specific: Trade-offs balanced không? (AI có bias vendor nào không?)
- [ ] ADR-specific: Consequences realistic không?

---

### SA-03: NFR Checklist theo ISO 25010

| | |
|---|---|
| **Pattern ID** | SA-03 |
| **Tên** | NFR-Checklist-ISO25010 |
| **Mục đích** | Tạo NFR checklist đầy đủ theo ISO/IEC 25010:2023 product quality model |
| **Vai trò** | SA (Author), BA (Input — business priorities), QA (Reviewer — testability) |
| **Evidence Level** | [Proven] — Cross-cutting SA task |
| **Tool khuyến nghị** | Claude / ChatGPT (WebUI) |

#### Input cần chuẩn bị

1. Project context: loại hệ thống, domain, user base
2. Business priorities: NFR nào quan trọng nhất (performance? security? availability?)
3. Existing NFR constraints (nếu có từ BRD/SRS)

#### Prompt Template

```
Bạn là Solution Architect. Tạo NFR checklist theo ISO/IEC 25010:2023 product quality model cho hệ thống dưới đây.

## System Context
[Mô tả: loại system, domain, user base, scale, deployment model]

## Business Priorities (rank 1-3)
[Ví dụ: 1. Performance, 2. Security, 3. Availability]

## Existing Constraints
[NFR constraints từ BRD/SRS nếu có]

## Output: NFR Checklist
Với MỖI quality characteristic trong ISO/IEC 25010:2023, tạo:

| Category | Sub-characteristic | NFR ID | Description | Threshold/Target | Priority | Testable? |
|---|---|---|---|---|---|---|

ISO/IEC 25010:2023 categories:
1. Functional Suitability (Correctness, Completeness, Appropriateness)
2. Performance Efficiency (Time behaviour, Resource utilization, Capacity)
3. Compatibility (Co-existence, Interoperability)
4. Interaction Capability (Appropriateness recognizability, Learnability, Operability, User error protection, Accessibility)
5. Reliability (Availability, Fault tolerance, Recoverability)
6. Security (Confidentiality, Integrity, Non-repudiation, Accountability, Authenticity, Resistance)
7. Maintainability (Modularity, Reusability, Analysability, Modifiability, Testability)
8. Flexibility (Adaptability, Scalability, Installability, Replaceability)

Quy tắc:
- Mỗi NFR phải có threshold/target CỤ THỂ (không "fast", "secure")
- Đánh dấu [VERIFY] cho thresholds cần business confirm
- Priority: 🔴 Must / 🟡 Should / 🟢 Nice
- Testable: Yes/No/Partial
```

#### Good Example (trích đoạn)

```
| Category | Sub-char | NFR ID | Description | Threshold | Priority | Testable? |
|---|---|---|---|---|---|---|
| Performance | Time behaviour | NFR-PE-01 | API response time under normal load | ≤ 2s for 95th percentile (≤500 concurrent users) | 🔴 Must | Yes |
| Performance | Capacity | NFR-PE-02 | System handles peak load | ≥ 1000 concurrent users without degradation [VERIFY] | 🔴 Must | Yes |
| Security | Authenticity | NFR-SE-01 | Multi-factor authentication cho admin roles | MFA bắt buộc cho role Admin, Super Admin | 🔴 Must | Yes |
| Reliability | Availability | NFR-RE-01 | System uptime | ≥ 99.9% monthly (excl. planned maintenance) | 🔴 Must | Yes |
| Reliability | Recoverability | NFR-RE-02 | Recovery time after failure | RTO ≤ 1h, RPO ≤ 15min [VERIFY] | 🟡 Should | Partial |
```

#### Anti-pattern (BAD)

```
NFR-01: The system should be fast
NFR-02: The system should be secure
NFR-03: The system should be available
```

**Tại sao xấu:** Không measurable. Không testable. Không map ISO 25010. Không priority.

#### Review Checklist

- [ ] RC1 — Thresholds realistic cho project context không? [VERIFY all]
- [ ] RC2 — Cover đủ 8 categories ISO 25010:2023 không?
- [ ] RC6 — QA có test được mỗi NFR không? (Testable = Yes/Partial)
- [ ] NFR-specific: Business priorities reflect đúng trong priority ranking không?
- [ ] NFR-specific: Missing NFR nào specific cho domain? (compliance, accessibility, etc.)

---

### SA-04: API Spec Draft (OpenAPI)

| | |
|---|---|
| **Pattern ID** | SA-04 |
| **Tên** | API-Spec-Draft |
| **Mục đích** | Tạo OpenAPI spec skeleton từ requirements |
| **Vai trò** | SA (Author), Dev Lead (Reviewer — implementation feasibility) |
| **Evidence Level** | [Emerging] — P2.3 trong Roadmap v1 |
| **Tool khuyến nghị** | Claude / ChatGPT (WebUI). API khi team có >5 APIs/sprint. |

#### Input cần chuẩn bị

1. Requirements liên quan đến API (functional + NFR)
2. Resource/entity list (User, Order, Product, etc.)
3. Auth model (OAuth2, API key, JWT, etc.)
4. Existing API conventions (nếu có: naming, versioning, error format)

#### Prompt Template

```
Bạn là Solution Architect. Tạo OpenAPI 3.0 spec skeleton cho API dưới đây.

## API Context
[Mô tả: API cho ai dùng, mục đích, domain]

## Resources/Entities
[Liệt kê: User, Order, Product, etc. + key fields mỗi entity]

## Functional Requirements
[Paste requirements liên quan đến API operations]

## Auth Model
[OAuth2 / API Key / JWT + scope/permission model]

## API Conventions
[Naming: camelCase/snake_case; Versioning: URL path /v1/; Error format: RFC 7807; Pagination: cursor/offset]

## Output: OpenAPI 3.0 YAML
Tạo spec gồm:
- info (title, version, description)
- servers
- paths (CRUD cho mỗi resource + business-specific endpoints)
- components/schemas (request/response models)
- components/securitySchemes
- Mỗi endpoint có: summary, description, parameters, requestBody, responses (200, 400, 401, 403, 404, 500)

Đánh dấu # [VERIFY] cho business logic, validation rules, specific thresholds.
Đánh dấu # [DECISION NEEDED] cho design choices SA cần chốt.
```

#### Good Example (trích đoạn)

```yaml
paths:
  /v1/orders:
    post:
      summary: Tạo đơn hàng mới
      description: Customer tạo đơn hàng từ giỏ hàng. Requires authentication.
      operationId: createOrder
      tags: [Orders]
      security:
        - bearerAuth: [order:write]
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/CreateOrderRequest'
      responses:
        '201':
          description: Đơn hàng tạo thành công
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/OrderResponse'
        '400':
          description: Validation error (giỏ hàng trống, dưới minimum order) # [VERIFY minimum]
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/ErrorResponse'
        '401':
          description: Unauthorized
        '429':
          description: Rate limit exceeded # [VERIFY rate limit threshold]
```

#### Anti-pattern (BAD)

```yaml
paths:
  /orders:
    post:
      summary: Create order
      responses:
        '200':
          description: Success
```

**Tại sao xấu:** Không auth. Sai HTTP status (201 cho creation, không 200). Không error responses. Không schema. Không versioning.

#### Review Checklist

- [ ] RC1 — HTTP methods, status codes đúng REST conventions?
- [ ] RC4 — Naming conventions consistent? (camelCase vs snake_case)
- [ ] RC5 — Không expose sensitive fields trong response? (password, internal IDs)
- [ ] API-specific: Auth model đúng? Security schemes complete?
- [ ] API-specific: Error responses cover đủ cases? (400, 401, 403, 404, 429, 500)
- [ ] API-specific: [VERIFY] items đã check business rules chưa?

---

## QA Prompts

### QA-01: Sinh Test Cases từ AC

| | |
|---|---|
| **Pattern ID** | QA-01 |
| **Tên** | TC-from-AC |
| **Mục đích** | Sinh test cases từ Acceptance Criteria (Gherkin format) |
| **Vai trò** | QA (Author), QA Lead (Reviewer) |
| **Evidence Level** | [Proven] — P1.7 trong Roadmap v1 |
| **Tool khuyến nghị** | Claude / ChatGPT (WebUI). API cho batch >10 AC. |

#### Input cần chuẩn bị

1. AC list (Gherkin format — Given/When/Then)
2. Domain business rules (validation, constraints)
3. Test data constraints (data ranges, formats, sample values)
4. System boundaries (external APIs, databases, file systems)

#### Prompt Template

```
Bạn là QA Engineer có kinh nghiệm theo chuẩn ISTQB CTFL v4.0.1 (2024). Sinh test cases từ Acceptance Criteria dưới đây.

## Acceptance Criteria
[Paste AC list dạng Gherkin]

## Domain Business Rules
[Paste rules: validation, constraints, dependencies]

## Test Data Constraints
[Data ranges, formats, sample values, prohibited values]

## Output Format
Với MỖI AC scenario, tạo test cases:

| TC ID | AC Ref | Type | Preconditions | Steps | Test Data | Expected Result | Priority |
|---|---|---|---|---|---|---|---|

Types (theo ISTQB):
- Positive: Happy path
- Negative: Invalid input, error handling
- Boundary: Min, max, zero, empty, null
- Edge: Rare conditions, race conditions, timeouts

Quy tắc:
- Mỗi AC scenario → ≥3 test cases (1 positive + 1 negative + 1 boundary)
- Test data phải CỤ THỂ (không "valid data")
- Steps phải step-by-step (1. Navigate to... 2. Enter... 3. Click...)
- Expected result phải verifiable (không "hệ thống hoạt động đúng")
- Priority: P1 (Critical) / P2 (High) / P3 (Medium) / P4 (Low)
```

#### Good Example (trích đoạn)

```
| TC ID | AC Ref | Type | Preconditions | Steps | Test Data | Expected Result | Priority |
|---|---|---|---|---|---|---|---|
| TC-001 | BRQ-001-S1 | Positive | User logged in; Cart has 2 items, total 150.000 VNĐ | 1. Navigate to Cart page 2. Verify items displayed 3. Click "Đặt hàng" 4. Wait for confirmation | User: test_user@mail.com; Cart: [Item-A x1, Item-B x1] | Order created with status "Pending"; Confirmation email received within 30s | P1 |
| TC-002 | BRQ-001-S2 | Negative | User logged in; Cart empty | 1. Navigate to Cart page 2. Verify cart shows "0 items" 3. Click "Đặt hàng" | User: test_user@mail.com; Cart: empty | Error message "Giỏ hàng trống..."; No order created in DB | P1 |
| TC-003 | BRQ-001-S3 | Boundary | User logged in; Cart total = 49.999 VNĐ | 1. Add item 49.999 VNĐ to cart 2. Click "Đặt hàng" | Cart total: 49.999 VNĐ [VERIFY min order] | Error: "Đơn hàng tối thiểu 50.000 VNĐ" | P2 |
| TC-004 | BRQ-001-S3 | Boundary | User logged in; Cart total = 50.000 VNĐ | 1. Add item 50.000 VNĐ to cart 2. Click "Đặt hàng" | Cart total: 50.000 VNĐ | Order created successfully (boundary accepted) | P2 |
```

#### Anti-pattern (BAD)

```
TC-001: Test the order feature. Steps: Create an order. Expected: Order is created.
TC-002: Test with invalid data. Expected: Error shown.
```

**Tại sao xấu:** Không có preconditions. Steps quá chung. Test data không cụ thể. Expected result không verifiable. Không có types (positive/negative/boundary). Không truy về AC.

#### Review Checklist

- [ ] RC1 — Business rules trong test data đúng không?
- [ ] RC2 — Mỗi AC có ≥3 TC (positive + negative + boundary)?
- [ ] RC6 — Tester mới đọc TC có thực hiện được ngay không?
- [ ] TC-specific: Test data realistic, cụ thể? (không "valid data", "test123")
- [ ] TC-specific: Expected results verifiable? (có check DB, email, UI cụ thể?)
- [ ] TC-specific: AC coverage ≥80%? (AC nào chưa có TC?)

---

### QA-02: Review Test Plan

| | |
|---|---|
| **Pattern ID** | QA-02 |
| **Tên** | Test-Plan-Review |
| **Mục đích** | Review Test Plan theo ISO/IEC/IEEE 29119-2:2021 + ISTQB |
| **Vai trò** | QA Lead (Author), PM (Reviewer — resource/timeline) |
| **Evidence Level** | [Emerging] — Cross-cutting QA task |
| **Tool khuyến nghị** | Claude Projects (WebUI) |

#### Input cần chuẩn bị

1. Test Plan document (full text)
2. SRS / Requirements list (scope reference)
3. Project timeline + resource constraints

#### Prompt Template

```
Bạn là QA Manager. Review Test Plan dưới đây theo ISO/IEC/IEEE 29119-2:2021 requirements và ISTQB CTFL v4.0.1 terminology.

## Test Plan
[Paste Test Plan]

## SRS / Requirements (scope reference)
[Paste requirements list hoặc summary]

## Project Timeline
[Key dates: dev complete, test start, test end, release date]

## Review Checklist
Đánh giá Test Plan theo các tiêu chí:
1. **Scope**: Test plan cover đủ SRS requirements không? Có liệt kê out-of-scope rõ không?
2. **Test Levels**: Đủ test levels không? (Unit, Integration, System, UAT — theo ISTQB)
3. **Test Types**: Có functional + non-functional testing? (Performance, Security, Usability)
4. **Entry/Exit Criteria**: Rõ ràng, measurable? (không "test đủ")
5. **Test Environment**: Specifications đủ chi tiết?
6. **Resources & Schedule**: Realistic với timeline? Risk nếu slip?
7. **Risk-based Testing**: Có risk assessment? High-risk areas có more coverage?
8. **Defect Management**: Process rõ? Severity/priority definitions?
9. **Traceability**: RTM link requirements → test cases?
10. **Reporting**: Metrics? Reports? Frequency?

## Output
Bảng findings + Overall assessment (Approve / Approve with conditions / Rework)
```

#### Good Example (trích đoạn)

```
| # | Tiêu chí | Status | Finding | Recommendation |
|---|---|---|---|---|
| 1 | Scope | ⚠️ Partial | SRS-015 (multi-currency) không trong test scope | Thêm test cases cho currency conversion hoặc ghi rõ "deferred to phase 2" |
| 4 | Entry/Exit Criteria | ❌ Fail | Exit criteria ghi "tất cả test cases pass" — unrealistic | Sửa: "≥95% TC pass; 0 Critical/High severity open; All P1 scenarios pass" |
| 7 | Risk-based Testing | ⚠️ Partial | Không có risk assessment cho payment module — high business impact | Thêm risk matrix; payment module cần extra coverage (security + performance) |
```

#### Anti-pattern (BAD)

```
Test plan is comprehensive and well-written. All sections are present. Recommend proceeding with testing.
```

**Tại sao xấu:** Không specific findings. Không check từng tiêu chí. "Comprehensive" dựa trên gì?

#### Review Checklist

- [ ] RC1 — AI findings chính xác? (check 3-5 findings bằng tay)
- [ ] RC3 — Findings consistent với SRS cross-reference?
- [ ] RC6 — Recommendations actionable cho QA team?
- [ ] QA-specific: False positive rate low? (AI không flag nhầm quá nhiều)

---

### QA-03: DoD Compliance Check

| | |
|---|---|
| **Pattern ID** | QA-03 |
| **Tên** | DoD-Compliance-Check |
| **Mục đích** | Kiểm tra Definition of Done compliance cho Sprint/Release |
| **Vai trò** | QA (Checker), SM (Facilitator), PO (Accept) |
| **Evidence Level** | [Proven] — Cross-cutting task |
| **Tool khuyến nghị** | Claude / ChatGPT (WebUI) |

#### Input cần chuẩn bị

1. DoD checklist (từ team agreement)
2. Sprint/Release output list (completed items + evidence)
3. Test results summary

#### Prompt Template

```
Bạn là QA Engineer. Kiểm tra DoD compliance cho Sprint/Release dưới đây.

## Definition of Done (team DoD)
[Paste DoD checklist. Ví dụ:
- Code reviewed & merged
- Unit tests ≥80% coverage
- Integration tests pass
- No Critical/High bugs open
- Documentation updated
- Release notes written
- Performance test pass (if applicable)
- Security scan clean (if applicable)]

## Completed Items
[Paste list: User Story ID, title, AC status, test results]

## Test Results Summary
[Pass/Fail counts, coverage, open defects by severity]

## Output Format
| DoD Item | Status (✅/❌/⚠️) | Evidence | Gap (nếu có) | Action needed |
|---|---|---|---|---|

Tóm tắt: Sprint/Release ready? Yes/No/Conditional. Blockers nếu có.
```

#### Good Example (trích đoạn)

```
| DoD Item | Status | Evidence | Gap | Action |
|---|---|---|---|---|
| Code reviewed & merged | ✅ | All 8 PRs merged; 2 approvals each | — | — |
| Unit tests ≥80% | ⚠️ | Overall 82%, nhưng Payment module chỉ 65% | Payment module dưới threshold | Thêm unit tests cho PaymentService (est. 4h) |
| No Critical/High open | ❌ | 1 High bug: BUG-234 "Incorrect total khi apply discount" | Blocker | Fix BUG-234 trước release |
| Security scan clean | ✅ | Snyk scan 0 Critical, 2 Medium (accepted risk) | — | — |

**Sprint ready: Conditional** — fix BUG-234 + Payment module unit tests.
```

#### Anti-pattern (BAD)

```
All DoD items look good. Sprint is ready for release.
```

**Tại sao xấu:** Không check từng item. Không evidence. Nếu có 1 item fail mà không phát hiện = risk.

#### Review Checklist

- [ ] RC1 — Evidence references chính xác? (check PR numbers, bug IDs)
- [ ] RC2 — Tất cả DoD items đã check? Không bỏ sót?
- [ ] RC6 — PO đọc xong biết quyết định accept/reject?
- [ ] DoD-specific: Thresholds check đúng? (coverage %, bug counts)

---

## PM Prompts

### PM-01: Weekly Status Report Draft

| | |
|---|---|
| **Pattern ID** | PM-01 |
| **Tên** | Weekly-Report-Draft |
| **Mục đích** | Tạo weekly status report draft từ project data |
| **Vai trò** | PM (Author), Delivery Manager (Reviewer) |
| **Evidence Level** | [Proven] — Cross-cutting PM task |
| **Tool khuyến nghị** | Claude / ChatGPT (WebUI) |

#### Input cần chuẩn bị

1. Sprint/iteration status (completed, in-progress, blocked)
2. Key metrics (velocity, burndown, defect trends)
3. Risk register updates (new risks, changes, closed)
4. Blockers and escalations
5. Key decisions made this week

#### Prompt Template

```
Bạn là Project Manager. Tạo weekly status report cho tuần [date range].

## Sprint/Iteration Status
[Paste: completed items, in-progress, blocked. % completion.]

## Key Metrics
[Velocity: X SP. Burndown: on track / behind / ahead. Defects: X open, Y closed.]

## Risks & Issues
[New risks, risk changes, blockers, escalations]

## Key Decisions
[Decisions made this week: who decided, what, impact]

## Stakeholder Audience
[Who reads this: PM Director, Client, Internal team]

## Report Format
### 1. Executive Summary (3-5 bullets, RAG status: 🟢/🟡/🔴)
### 2. Sprint Progress (table: story, status, % done, blocker)
### 3. Key Metrics (table: metric, this week, trend)
### 4. Risks & Issues (table: ID, description, impact, mitigation, owner, status)
### 5. Decisions Made
### 6. Next Week Plan (top 3 priorities)
### 7. Escalations / Help Needed

Viết concise, action-oriented. Executive summary đủ để skip phần còn lại nếu cần.
RAG status: 🟢 On track, 🟡 At risk (có mitigation), 🔴 Off track (cần escalation).
```

#### Good Example (trích đoạn)

```
## 1. Executive Summary — Tuần 10/03 – 14/03/2026
Overall Status: 🟡 AT RISK

- Sprint 7 đạt 78% planned SP (31/40 SP). Behind do dependency với Payment API chưa ready.
- 1 High defect mới (BUG-234) — đang fix, ETA Friday.
- Risk RK-05 (3rd party API delay) upgraded từ Medium → High.
- Decision: Defer multi-currency feature sang Sprint 9 (PO approved).
- Escalation: Cần DevOps support cho staging environment trước thứ 4.
```

#### Anti-pattern (BAD)

```
This week went well. We made good progress. There are some risks but we're managing them. Everything is on track.
```

**Tại sao xấu:** Không data cụ thể. Không RAG status. "Good progress" = bao nhiêu %? "Some risks" = risk nào? Stakeholders không thể act on this.

#### Review Checklist

- [ ] RC1 — Metrics numbers đúng? (cross-check Jira/board)
- [ ] RC3 — RAG status reflect đúng tình hình?
- [ ] RC5 — Không leak sensitive info cho wrong audience?
- [ ] RC6 — Executive summary đủ info để stakeholder quyết định?
- [ ] PM-specific: Blockers và escalations rõ ràng, có owner?

---

### PM-02: Risk Assessment

| | |
|---|---|
| **Pattern ID** | PM-02 |
| **Tên** | Risk-Assessment |
| **Mục đích** | Identify và assess risks cho project/sprint |
| **Vai trò** | PM (Author), SA/BA/QA (Contributors), Delivery Manager (Reviewer) |
| **Evidence Level** | [Emerging] — Cross-cutting task. AI suggest, human validate. |
| **Tool khuyến nghị** | Claude / ChatGPT (WebUI) |

#### Input cần chuẩn bị

1. Project context (domain, tech stack, team size, timeline)
2. Current risk register (nếu có)
3. Recent events (issues, blockers, changes, dependencies)
4. Stakeholder concerns

#### Prompt Template

```
Bạn là PM với kinh nghiệm risk management theo PMBOK 7th Edition (2021). Identify và assess risks cho project context dưới đây.

## Project Context
[Mô tả: domain, tech stack, team, timeline, budget, complexity]

## Current Risk Register
[Paste existing risks nếu có]

## Recent Events / Changes
[Issues, blockers, scope changes, dependency updates tuần này]

## Output Format
| Risk ID | Category | Description | Probability (H/M/L) | Impact (H/M/L) | Risk Score | Mitigation | Contingency | Owner | Status |
|---|---|---|---|---|---|---|---|---|---|

Categories: Technical, Resource, Schedule, Scope, External, Financial, Quality, Security
Risk Score: H×H=Critical, H×M/M×H=High, M×M=Medium, rest=Low

Sau bảng:
- Top 3 risks cần action ngay
- Risks mới so với register hiện tại
- Risks cần escalate

Đánh dấu [VERIFY] cho probability/impact mà AI không chắc chắn.
Đánh dấu [NEEDS HUMAN] cho risks cần domain knowledge để đánh giá.
```

#### Good Example (trích đoạn)

```
| Risk ID | Category | Description | Prob | Impact | Score | Mitigation | Owner |
|---|---|---|---|---|---|---|---|
| RK-NEW-01 | External | Payment gateway API v2 deprecation announced for June — team đang dùng v1 | H | H | Critical | Start migration plan Sprint 8; allocate 1 dev full-time | SA Lead |
| RK-NEW-02 | Resource | Senior dev resign effective April [VERIFY] | M | H | High | Knowledge transfer Sprint 8-9; hiring request submitted | PM |
| RK-05 | Schedule | 3rd party API delay (upgraded from M→H) | H | M | High | Stub API for testing; parallel track with vendor | Dev Lead |
```

#### Anti-pattern (BAD)

```
The project has typical software development risks including timeline delays, resource constraints, and technical challenges. These are being managed.
```

**Tại sao xấu:** Quá chung. Không specific risk nào. Không actionable. "Being managed" — managed bằng cách nào?

#### Review Checklist

- [ ] RC1 — Probability/Impact ratings realistic? [VERIFY]
- [ ] RC6 — Mitigations actionable? (có ai, làm gì, khi nào)
- [ ] Risk-specific: AI có miss risks mà bạn biết? (domain knowledge)
- [ ] Risk-specific: [NEEDS HUMAN] items reviewed bởi đúng người?

---

### PM-03: Stakeholder Communication

| | |
|---|---|
| **Pattern ID** | PM-03 |
| **Tên** | Stakeholder-Comms |
| **Mục đích** | Draft stakeholder communication (email, update, escalation) |
| **Vai trò** | PM (Author), Delivery Manager (Reviewer nếu escalation) |
| **Evidence Level** | [Proven] — Cross-cutting PM task |
| **Tool khuyến nghị** | Claude / ChatGPT (WebUI) |

#### Input cần chuẩn bị

1. Context: lý do communication (status update, escalation, decision request, bad news)
2. Audience: ai đọc, level gì, mối quan tâm chính
3. Key facts: data, dates, impacts cụ thể
4. Desired outcome: audience cần làm gì sau khi đọc

#### Prompt Template

```
Bạn là PM cần gửi [type: status update / escalation / decision request / bad news delivery] cho [audience].

## Context
[Lý do gửi. Sự kiện/vấn đề gì xảy ra.]

## Audience
[Ai đọc: Client PM, CTO, Sponsor, Team. Mối quan tâm chính của họ.]

## Key Facts
[Data cụ thể: dates, numbers, impacts]

## Desired Outcome
[Audience cần: acknowledge / decide / approve / provide resource / reschedule]

## Tone & Constraints
[Professional/friendly. Length: short (3-5 lines) / medium (1 page). Language: Vietnamese/English/bilingual.]

## Output
Draft communication. Include:
- Subject line (nếu email)
- Opening: context + why writing now
- Body: key facts + impact + options (nếu decision request)
- Close: clear ask / next steps / deadline for response
- Đánh dấu [CUSTOMIZE] cho phần cần PM adjust giọng điệu
```

#### Good Example (trích đoạn)

```
Subject: [Action Required] Sprint 7 Delay — Payment Module Impact Assessment

Hi [Client PM name] [CUSTOMIZE],

Cập nhật nhanh về Sprint 7: chúng tôi gặp delay 3 ngày do Payment Gateway API v1 deprecation notice (tham khảo đính kèm).

**Impact:** Release date dự kiến lùi từ 28/03 → 31/03 (3 business days).
**Root cause:** Payment API migration từ v1 → v2 cần thêm 2 Sprint Points.
**Mitigation:** Đã reallocate 1 senior dev; parallel testing để giảm delay.

**Cần từ anh/chị:** Confirm chấp nhận timeline mới 31/03 hoặc chúng tôi discuss scope adjustment trong call ngày mai.

Deadline phản hồi: Thứ 4 (12/03) trước 5PM.

Best regards,
[PM name] [CUSTOMIZE]
```

#### Anti-pattern (BAD)

```
Hi Team,
Just wanted to let you know there's a small delay. Nothing to worry about. Will keep you posted.
Thanks!
```

**Tại sao xấu:** "Small delay" — bao nhiêu ngày? "Nothing to worry" — không đúng nếu impact lớn. Không impact analysis. Không ask. Không timeline.

#### Review Checklist

- [ ] RC1 — Dates, numbers, names đúng?
- [ ] RC5 — Không leak info ra wrong audience? (client vs internal)
- [ ] RC6 — Clear ask/outcome? Deadline response?
- [ ] Comms-specific: Tone phù hợp audience?
- [ ] Comms-specific: [CUSTOMIZE] sections đã personalize chưa?

---

## DevOps Prompts

### DevOps-01: Runbook Draft

| | |
|---|---|
| **Pattern ID** | DevOps-01 |
| **Tên** | Runbook-Draft |
| **Mục đích** | Tạo operational runbook cho service/system |
| **Vai trò** | DevOps/SRE (Author), Dev Lead (Reviewer), Ops Team (User) |
| **Evidence Level** | [Proven] — P1.9 trong Roadmap v1 |
| **Tool khuyến nghị** | Claude / ChatGPT (WebUI) |

#### Input cần chuẩn bị

1. Service/system architecture overview
2. Common operational procedures (deployment, restart, scaling)
3. Known failure modes + workarounds
4. Monitoring/alerting setup (dashboards, alert rules)
5. Contact list (on-call, escalation)

#### Prompt Template

```
Bạn là DevOps Engineer. Tạo operational runbook cho service dưới đây.

## Service Overview
[Tên service, tech stack, deployment model, dependencies]

## Architecture (brief)
[Components, data flow, external integrations]

## Common Procedures needed
[Deployment steps, restart, scaling up/down, log access, backup/restore]

## Known Failure Modes
[List lỗi hay gặp + workaround hiện tại]

## Monitoring Setup
[Dashboard URLs, alert rules, metrics to watch]

## Runbook Template
Tạo runbook theo structure:

### 1. Service Overview
- Name, owner, criticality (P1/P2/P3)
- Architecture diagram reference
- Dependencies (upstream/downstream)

### 2. Health Checks
- Endpoint: [health check URL]
- Expected response + latency threshold
- Dashboard: [monitoring URL]

### 3. Standard Operating Procedures
Mỗi procedure:
- **Trigger**: Khi nào thực hiện
- **Prerequisites**: Cần gì trước khi bắt đầu
- **Steps**: Step-by-step commands (copy-paste được)
- **Verification**: Cách confirm procedure thành công
- **Rollback**: Cách revert nếu fail

### 4. Incident Response
Mỗi known failure mode:
- **Symptom**: Biểu hiện (alert, error log, user report)
- **Diagnosis**: Commands để check
- **Fix**: Step-by-step resolution
- **Escalation**: Khi nào escalate, gọi ai

### 5. Contact & Escalation
- On-call rotation
- Escalation path + SLA

Đánh dấu [VERIFY] cho URLs, thresholds, commands cần kiểm tra.
Đánh dấu [CUSTOMIZE] cho environment-specific values.
```

#### Good Example (trích đoạn)

```
### 3.1 Deploy New Version

**Trigger:** New release approved; PR merged to main branch
**Prerequisites:** Staging deploy successful; Smoke tests pass
**Steps:**
1. Check current version:
   ```
   kubectl get pods -n production -l app=order-service -o jsonpath='{.items[0].spec.containers[0].image}'
   ```
2. Deploy new version:
   ```
   kubectl set image deployment/order-service order-service=registry.company.com/order-service:v2.3.1 -n production
   ```
3. Monitor rollout:
   ```
   kubectl rollout status deployment/order-service -n production --timeout=300s
   ```
**Verification:** Health check returns 200; Grafana dashboard shows no error spike for 10 min
**Rollback:**
   ```
   kubectl rollout undo deployment/order-service -n production
   ```
```

#### Anti-pattern (BAD)

```
To deploy: push to production. If something goes wrong, rollback.
```

**Tại sao xấu:** Không có commands. "Push to production" bằng cách nào? "Rollback" bằng lệnh gì? Ops team lúc 2AM không thể dùng được.

#### Review Checklist

- [ ] RC1 — Commands đúng, chạy được? [VERIFY trên staging]
- [ ] RC2 — Đủ procedures cho: deploy, restart, scale, incident?
- [ ] RC5 — Không chứa credentials, secrets trong runbook?
- [ ] RC6 — On-call engineer lúc 2AM đọc và follow được không?
- [ ] Runbook-specific: Rollback steps có cho MỌI procedure?
- [ ] Runbook-specific: [VERIFY] URLs, thresholds đã kiểm tra?

---

### DevOps-02: Incident Postmortem

| | |
|---|---|
| **Pattern ID** | DevOps-02 |
| **Tên** | Postmortem-Draft |
| **Mục đích** | Tạo blameless incident postmortem draft |
| **Vai trò** | Incident Commander (Author), Eng Manager (Reviewer) |
| **Evidence Level** | [Emerging] — P2.7 trong Roadmap v1 |
| **Tool khuyến nghị** | Claude / ChatGPT (WebUI) |

#### Input cần chuẩn bị

1. Incident timeline (chronological events)
2. Impact data (duration, affected users, revenue impact if known)
3. Root cause analysis (technical details)
4. Actions taken during incident
5. Participants (who was involved in resolution)

#### Prompt Template

```
Bạn là Incident Commander. Tạo blameless postmortem cho incident dưới đây.

## Incident Data
[Paste: timeline, impact, root cause, actions taken, participants]

## Postmortem Template
# Incident Postmortem: [Title]
## Metadata
- Date: [incident date]
- Duration: [start → end]
- Severity: [P1/P2/P3]
- Incident Commander: [name]
- Author: [name]

## Summary (3 lines max)
## Impact
- Users affected: [number/percentage]
- Duration: [minutes/hours]
- Revenue impact: [if applicable, VERIFY]
- SLA impact: [if applicable]

## Timeline (chronological, UTC)
| Time | Event | Actor |
|---|---|---|

## Root Cause Analysis
- Primary cause
- Contributing factors (≥2)
- Why was this not caught earlier?

## What Went Well
## What Went Poorly
## Action Items
| # | Action | Owner | Priority | Deadline | Status |
|---|---|---|---|---|---|

Types: Prevent recurrence, Improve detection, Improve response

## Lessons Learned

CRITICAL RULES:
- BLAMELESS: Không blame cá nhân. Focus systems/processes.
- Tone factual, không defensive.
- Action items phải specific, có owner, có deadline.
- Đánh dấu [VERIFY] cho timeline, numbers cần cross-check.
```

#### Good Example (trích đoạn)

```
## Summary
Order Service outage 45 phút do database connection pool exhaustion. ~2.500 users không thể đặt hàng. Root cause: missing connection timeout config sau migration tuần trước.

## Timeline
| Time (UTC) | Event | Actor |
|---|---|---|
| 14:23 | Alert: Order Service error rate >5% | PagerDuty |
| 14:25 | IC acknowledged; started investigation | IC: Minh |
| 14:32 | Identified: DB connection pool 100% used (max 50) | Minh |
| 14:38 | Attempted: Increase pool size to 100 → did not resolve | Dev: Huy |
| 14:45 | Root cause found: Missing idle connection timeout | Huy |
| 14:50 | Fix deployed: Added 30s idle timeout config | Huy |
| 15:08 | Service recovered; error rate back to baseline | Monitoring |

## Action Items
| # | Action | Owner | Priority | Deadline | Status |
|---|---|---|---|---|---|
| AI-01 | Add connection pool monitoring to Grafana dashboard | DevOps Lan | P1 | 17/03 | Open |
| AI-02 | Review all services for missing timeout configs | Dev Lead | P1 | 21/03 | Open |
| AI-03 | Add connection pool alert rule (>80% utilization) | DevOps Lan | P2 | 19/03 | Open |
```

#### Anti-pattern (BAD)

```
The incident happened because Huy forgot to configure the timeout after migration. He should have been more careful. We will make sure this doesn't happen again.
```

**Tại sao xấu:** BLAME cá nhân. Không blameless. "Should have been more careful" = không actionable. "Won't happen again" = wishful thinking, không có specific action items.

#### Review Checklist

- [ ] RC1 — Timeline accurate? [VERIFY với logs và participants]
- [ ] RC5 — Không blame cá nhân? Blameless tone?
- [ ] RC6 — Action items specific, có owner, deadline?
- [ ] Postmortem-specific: Root cause analysis sâu? (không chỉ surface cause)
- [ ] Postmortem-specific: Contributing factors identified?
- [ ] Postmortem-specific: "What went well" included? (not just negative)

---

### DevOps-03: Release Notes

| | |
|---|---|
| **Pattern ID** | DevOps-03 |
| **Tên** | Release-Notes-Gen |
| **Mục đích** | Tạo release notes từ changelogs, PRs, completed stories |
| **Vai trò** | DevOps/PM (Author), PM (Reviewer) |
| **Evidence Level** | [Proven] — P1.8 trong Roadmap v1 |
| **Tool khuyến nghị** | Claude / GitHub Copilot (WebUI / CLI) |

#### Input cần chuẩn bị

1. Changelog / Git log (commits from last release to current)
2. Completed user stories / tickets list
3. Known issues / limitations
4. Breaking changes (if any)
5. Target audience (end users / developers / ops team)

#### Prompt Template

```
Bạn là DevOps Engineer. Tạo release notes cho version [X.Y.Z].

## Changelog / Commits
[Paste git log hoặc changelog entries]

## Completed Stories / Tickets
[Paste: ticket ID, title, type (feature/bugfix/improvement)]

## Known Issues
[Issues chưa fix trong release này]

## Breaking Changes
[API changes, config changes, migration required]

## Audience
[End users / Developers / Ops — giọng điệu phù hợp]

## Release Notes Format
# Release Notes — v[X.Y.Z] ([date])

## Highlights (top 3 features/changes — cho người không muốn đọc hết)

## New Features
- [FEAT-ID] Feature name — mô tả ngắn (1-2 câu)

## Improvements
- [IMP-ID] Improvement name — mô tả

## Bug Fixes
- [BUG-ID] Bug description — đã fix thế nào

## Breaking Changes ⚠️
- Mô tả change + migration guide

## Known Issues
- [KNOWN-ID] Issue description — workaround nếu có

## Technical Notes (cho developers/ops)
- Dependencies updated
- Configuration changes
- Migration steps

Viết cho audience: clear, concise, no jargon cho end users; technical chi tiết cho devs.
```

#### Good Example (trích đoạn)

```
# Release Notes — v2.3.0 (14/03/2026)

## Highlights
- 🆕 Multi-language support (Vietnamese, English, Japanese)
- ⚡ Order processing 40% faster (new caching layer)
- 🔒 MFA bắt buộc cho admin accounts

## New Features
- [FEAT-123] Multi-language UI — chuyển đổi ngôn ngữ trên menu Settings
- [FEAT-125] Bulk order export — download CSV cho ≤10.000 orders

## Bug Fixes
- [BUG-234] Fixed: Incorrect discount calculation khi apply 2+ coupon codes
- [BUG-237] Fixed: Timeout khi load order history >1000 records

## Breaking Changes ⚠️
- API endpoint `/api/orders` đổi thành `/api/v2/orders`. V1 deprecated, remove trong v3.0.
- Migration: chạy `./scripts/migrate_v2.3.sh` trước khi deploy. [VERIFY script path]
```

#### Anti-pattern (BAD)

```
v2.3.0 - Various improvements and bug fixes. Please update to the latest version.
```

**Tại sao xấu:** Không chi tiết. Users không biết có gì mới. Không breaking changes warning = risk. Không known issues = surprise.

#### Review Checklist

- [ ] RC1 — Feature/bug IDs link đúng tickets?
- [ ] RC2 — All completed items có trong notes? (cross-check sprint board)
- [ ] RC5 — Không leak internal details cho external audience?
- [ ] RC6 — End users đọc hiểu features mới? Devs biết migration steps?
- [ ] Release-specific: Breaking changes có migration guide?
- [ ] Release-specific: Known issues có workaround?

---

## Changelog

| Version | Date | Changes |
|---|---|---|
| v1.0 | 09/03/2026 | Tạo mới — 17 prompt patterns: BA (4), SA (4), QA (3), PM (3), DevOps (3). Input: Roadmap v1 + Gap Analysis v1.0 + AI Pilot Plan. |

---

## Tham chiếu Chéo (Cross-References)

| Nội dung | Tài liệu |
|---|---|
| Data classification + Review gates | SDLC_AI_Playbook_v1.docx (Ch.3, Ch.5) |
| Task → Tool mapping | SDLC_AI_Playbook_v1.docx (Ch.4) |
| Phase 1 task list (P1.1–P1.12) | SDLC_AI_Integration_Roadmap_v1.docx (Ch.2) |
| Phase 2 task list (P2.1–P2.10) | SDLC_AI_Integration_Roadmap_v1.docx (Ch.3) |
| Template structures | SDLC_Templates_Pack_v7.1.xlsx |
| ISO/IEC/IEEE 29148:2018 | SRS quality characteristics (BA-02) |
| ISO/IEC 25010:2023 | NFR checklist (SA-03) |
| ISTQB CTFL v4.0.1 (2024) | Test terminology (QA-01, QA-02) |
| OWASP Top 10:2021 | Security review (SA-01) |
| NIST SP 800-218 v1.1 (SSDF) | Security gates (SA-01) |
| PMBOK 7th (2021) | Risk management (PM-02) |
| Scrum Guide (2020) | DoD, Sprint (QA-03) |
