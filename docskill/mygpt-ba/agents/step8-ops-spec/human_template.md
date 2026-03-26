— Human Template

# Deployment & Ops Spec — {{ops_id}}
**QA ref:** {{qa_ref}}

## Environments

| ID | Name | Infrastructure | Deploy trigger | Backup |
|----|------|---------------|----------------|--------|
{{#each environments}}
| {{id}} | {{name}} | {{infrastructure}} | {{deploy_trigger}} | {{backup}} |
{{/each}}

## CI/CD Stages

| ID | Stage | Tool | Duration | Fail condition |
|----|-------|------|----------|----------------|
{{#each cicd_pipeline.stages}}
| {{id}} | {{name}} | {{tool}} | {{duration_min}} min | {{fail_condition}} |
{{/each}}

**Rollback:**
- Auto: {{cicd_pipeline.rollback_strategy.automatic}}
- Manual: `{{cicd_pipeline.rollback_strategy.manual_command}}`
- DB: {{cicd_pipeline.rollback_strategy.db_rollback}}

## Monitoring Alerts

| ID | Metric | Điều kiện | Severity | Kênh | Action |
|----|--------|----------|---------|------|--------|
{{#each monitoring_alerts}}
| {{id}} | {{metric}} | {{condition}} | {{severity}} | {{channel}} | {{action}} |
{{/each}}

## DR Plan

| Scenario | RTO | RPO | Recovery steps |
|---------|-----|-----|----------------|
{{#each dr_plan}}
| {{scenario}} | {{rto}} | {{rpo}} | {{recovery_steps | join " → "}} |
{{/each}}

## Go-Live Checklist
**Technical:**
{{#each go_live_checklist.technical}}
- [ ] {{this}}
{{/each}}

**Process:**
{{#each go_live_checklist.process}}
- [ ] {{this}}
{{/each}}

**Post-launch 48h:**
{{#each go_live_checklist.post_launch_48h}}
- [ ] {{this}}
{{/each}}