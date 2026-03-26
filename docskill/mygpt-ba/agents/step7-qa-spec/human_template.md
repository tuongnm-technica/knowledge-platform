— Human Template

# QA Review — {{qa_id}}
**Spec ref:** {{spec_ref}}

## Consistency Checks

| ID | Vấn đề | Location A | Location B | Severity | Verdict | Sửa |
|----|--------|-----------|-----------|---------|---------|-----|
{{#each consistency_checks}}
| {{id}} | {{issue}} | {{location_a}} | {{location_b}} | {{severity}} | {{verdict}} | {{fix}} |
{{/each}}

## Test Cases — Unit (Owner: Developer)
| ID | Module | Test | Expected | Tag |
|----|--------|------|---------|-----|
{{#each unit_tests}}
| {{id}} | {{module}} | {{test}} | {{expected}} | {{regression_tag}} |
{{/each}}

## Test Cases — E2E (Owner: QA Team)
| ID | UC | Title | Priority | Tag |
|----|-----|-------|---------|-----|
{{#each e2e_tests}}
| {{id}} | {{uc_ref}} | {{title}} | {{priority}} | {{regression_tag}} |
{{/each}}

## UAT Exit Criteria
| Criteria | Threshold | Current | Status |
|---------|-----------|---------|--------|
{{#each uat_plan.exit_criteria}}
| {{criteria}} | {{threshold}} | {{current}} | — |
{{/each}}

## Regression Strategy
| Set | Trigger | TCs included | Est. run time |
|-----|---------|-------------|--------------|
{{#each regression_strategy}}
| {{set}} | {{trigger}} | {{tc_included}} | {{estimated_run_min}} min |
{{/each}}