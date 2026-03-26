— Human Template

# FE Technical Spec — {{spec_id}}
**Story ref:** {{story_ref}}

## Components

| ID | Tên | Loại | Props in | Events out |
|----|-----|------|----------|-----------|
{{#each components}}
| {{id}} | {{name}} | {{type}} | {{props_in | join ", "}} | {{events_out | join ", "}} |
{{/each}}

## UI State Matrix

| ID | Component | State | Visual | Actions | Trigger |
|----|-----------|-------|--------|---------|---------|
{{#each ui_states}}
| {{id}} | {{component}} | {{state}} | {{visual}} | {{user_actions | join ", "}} | {{trigger}} |
{{/each}}

## Validation UX

| Field | Trigger | Error display | Button behavior | Reset |
|-------|---------|--------------|----------------|-------|
{{#each validation_ux}}
| {{field}} | {{trigger}} | {{error_display}} | {{button_behavior}} | {{reset_behavior}} |
{{/each}}

## Performance Budget
- Bundle: **{{performance_budget.bundle_size_kb_gzipped}}KB** gzipped
- LCP: **{{performance_budget.lcp_ms}}ms** | INP: **{{performance_budget.inp_ms}}ms** | CLS: **{{performance_budget.cls}}**
- Lazy loading: {{performance_budget.lazy_loading_strategy}}