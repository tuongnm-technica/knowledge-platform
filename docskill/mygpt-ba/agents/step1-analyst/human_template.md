— Human Template

# Intake Report — {{intake_id}}

**Nguồn:** {{source}} | **Ngày:** {{intake_id | date part}}

## Tóm tắt nghiệp vụ
{{summary}}

---

## Functional Requirements

| ID | Mô tả | Ưu tiên |
|----|-------|---------|
{{#each functional_requirements}}
| {{id}} | {{description}} | {{priority}} |
{{/each}}

## Non-Functional Requirements

| ID | Loại | Mô tả |
|----|------|-------|
{{#each non_functional_requirements}}
| {{id}} | {{category}} | {{description}} |
{{/each}}

## Business Rules

| ID | Ràng buộc | Nguồn |
|----|-----------|-------|
{{#each business_rules}}
| {{id}} | {{description}} | {{source}} |
{{/each}}

---

## Giả định
{{#each assumptions}}
- {{this}}
{{/each}}

## Ngoài phạm vi
{{#each out_of_scope}}
- {{this}}
{{/each}}

## Câu hỏi mở (cần làm rõ)
{{#each open_questions}}
- [ ] {{this}}
{{/each}}

---

## Traceability Seed

**Epic:** {{traceability_seed.epic}}  
**FR liên quan:** {{traceability_seed.fr_ids | join ", "}}

> _Handoff sang GPT-2: cung cấp file JSON này + context gốc._