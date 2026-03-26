— Human Template

# Review Report — {{review_id}}
**Intake ref:** {{intake_ref}}

## Functional Completeness

| ID | FR | Status | Vấn đề | Đề xuất |
|----|----|--------|--------|---------|
{{#each functional_checks}}
| {{id}} | {{fr_id}} | {{status}} | {{issue}} | {{suggestion}} |
{{/each}}

## Actor & Permission Gaps

| ID | Actor | FRs có quyền | FRs bị thiếu | Gap |
|----|-------|-------------|-------------|-----|
{{#each actor_permission_gaps}}
| {{id}} | {{actor}} | {{frs_granted | join ", "}} | {{frs_missing | join ", "}} | {{gap}} |
{{/each}}

## Business Rule Conflicts

| ID | BR-A | BR-B | Conflict | Đề xuất giải quyết |
|----|------|------|----------|-------------------|
{{#each br_conflicts}}
| {{id}} | {{br_a}} | {{br_b}} | {{conflict}} | {{resolution}} |
{{/each}}

## Edge Cases Bị Bỏ Sót

| ID | Scenario | FR liên quan | Impact | Behavior cần define |
|----|----------|-------------|--------|---------------------|
{{#each edge_cases}}
| {{id}} | {{scenario}} | {{related_fr}} | {{impact}} | {{required_behavior}} |
{{/each}}

## Data Flow Gaps

| ID | Vấn đề | Mô tả | FR liên quan | Cần làm rõ |
|----|--------|-------|-------------|-----------|
{{#each data_flow_gaps}}
| {{id}} | {{issue}} | {{description}} | {{related_fr}} | {{clarification_needed}} |
{{/each}}

## Integration Risks

| ID | Dependency | FR phụ thuộc | Risk | Fallback cần define |
|----|-----------|-------------|------|---------------------|
{{#each integration_risks}}
| {{id}} | {{dependency}} | {{related_frs | join ", "}} | {{risk_if_unavailable}} | {{fallback_needed}} |
{{/each}}

## Requirements Cải Tiến

| FR-ID | Cũ | Mới | Lý do |
|-------|-----|-----|-------|
{{#each improved_requirements}}
| {{fr_id}} | {{original}} | {{improved}} | {{reason}} |
{{/each}}

## Câu Hỏi Mở
{{#each open_questions}}
- [ ] {{this}}
{{/each}}

> **Handoff sang GPT-3:** FRs cải tiến: {{handoff_to_gpt3.improved_fr_ids | join ", "}}
> Flags: {{handoff_to_gpt3.flags | join " | "}}