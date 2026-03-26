— Human Template

# Release — {{release_note.system_name}} {{release_note.version}}

| Field | Value |
|-------|-------|
| Release ID | {{release_id}} |
| Ngày release | {{release_note.release_date}} |
| Release Manager | {{release_note.release_manager}} |
| Ops ref | {{ops_ref}} |

## Mục tiêu Release
{{#each release_note.objectives}}
{{@index_plus_1}}. {{this}}
{{/each}}

## Danh sách thay đổi

| Ref | Nội dung | Loại | Ghi chú |
|-----|---------|------|---------| 
{{#each release_note.changes}}
| {{ref_id}} | {{description}} | {{type}} | {{notes}} |
{{/each}}

## Change Request — {{change_request.id}}
**Risk level:** {{change_request.risk_level}} | **Status:** {{change_request.status}}

### Impact Analysis
**Modules:** {{change_request.impact_analysis.modules | map 'module' | join ", "}}
**APIs với breaking change:** {{change_request.impact_analysis.apis | filter 'breaking_change' | map 'endpoint' | join ", "}}
**DB tables cần migration:** {{change_request.impact_analysis.database | filter 'migration_required' | map 'table' | join ", "}}

### Rollback Plan
{{#each change_request.rollback_plan}}
{{@index_plus_1}}. {{this}}
{{/each}}

## Risk Log

| ID | Category | Mô tả | Impact | P | Status | Owner | Due |
|----|---------|-------|--------|---|--------|-------|-----|
{{#each risk_log}}
| {{id}} | {{category}} | {{description}} | {{impact}} | {{probability}} | {{status}} | {{owner}} | {{due_date}} |
{{/each}}