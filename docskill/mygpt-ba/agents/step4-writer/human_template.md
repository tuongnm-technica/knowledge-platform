— Human Template

# {{doc_type}} Document — {{doc_id}}
**Design ref:** {{design_ref}}

## Glossary

| Thuật ngữ | Định nghĩa | Ví dụ | Không nhầm với |
|-----------|-----------|-------|----------------|
{{#each glossary}}
| {{term}} | {{definition}} | {{example}} | {{not_to_confuse_with}} |
{{/each}}

## Phạm vi
**In scope:** {{scope.in_scope | join ", "}}
**Out of scope:** {{scope.out_of_scope | join ", "}}

## Use Cases

{{#each use_cases}}
### {{id}} — {{name}}
**Actor:** {{actor}} | **Trigger:** {{trigger}}
**FR refs:** {{fr_refs | join ", "}} | **BR refs:** {{br_refs | join ", "}}

**Preconditions:** {{preconditions | join "; "}}

**Main flow:**
{{#each main_flow}}
{{@index_plus_1}}. {{this}}
{{/each}}

**Exception flows:** {{exception_flows | join " · "}}

**Postconditions (success):** {{postconditions_success | join " · "}}
**Postconditions (failure):** {{postconditions_failure | join " · "}}

> FE Note: {{fe_technical_note}}
{{/each}}

## Validation Rules

| ID | Screen | Field | Type | Required | Trigger | UX | Error | Message |
|----|--------|-------|------|----------|---------|-----|-------|---------| 
{{#each validation_rules}}
| {{id}} | {{screen}} | {{field}} | {{data_type}} | {{required}} | {{trigger}} | {{ux_behavior}} | {{error_code}} | {{message}} |
{{/each}}

## Traceability Matrix

| FR | BR | UC | VR | TC (TBD) |
|----|-----|-----|-----|---------| 
{{#each traceability_matrix}}
| {{fr_id}} | {{br_id}} | {{uc_id}} | {{vr_ids | join ", "}} | {{tc_ids_tbd | join ", "}} |
{{/each}}