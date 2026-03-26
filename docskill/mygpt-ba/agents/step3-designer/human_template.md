— Human Template

# Solution Design — {{design_id}}
**Review ref:** {{review_ref}}

## Assumptions

| Item | Known | Assumed |
|------|-------|---------|
{{#each assumptions}}
| {{item}} | {{known}} | {{assumed}} |
{{/each}}

## Architecture: {{architecture.type}}
> {{architecture.rationale}}


{{architecture.ascii_diagram}}

## Architecture Decision Records

{{#each adrs}}
### {{id}}: {{title}} — *{{status}}*
| | |
|--|--|
| Context | {{context}} |
| Options | {{options}} |
| Decision | {{decision}} |
| Rationale | {{rationale}} |
| Trade-offs | {{tradeoffs}} |
| Review date | {{review_date}} |
{{/each}}

## Modules

| ID | Module | Trách nhiệm | Tech | Scale | Owner |
|----|--------|------------|------|-------|-------|
{{#each modules}}
| {{id}} | {{name}} | {{responsibilities}} | {{tech}} | {{scale_strategy}} | {{owner}} |
{{/each}}

## API Contract

| ID | Method | Endpoint | Auth | Idempotent | HTTP Status |
|----|--------|----------|------|-----------|------------|
{{#each api_contract}}
| {{id}} | {{method}} | {{endpoint}} | {{auth}} | {{idempotent}} | {{http_status | join ", "}} |
{{/each}}

## Risks

| ID | Risk | P | I | Mitigation | Owner |
|----|------|---|---|-----------|-------|
{{#each risks}}
| {{id}} | {{risk}} | {{probability}} | {{impact}} | {{mitigation}} | {{owner}} |
{{/each}}

## Scaling Roadmap

| Phase | Trigger | Actions |
|-------|---------|---------| 
{{#each scaling_roadmap}}
| {{phase}} | {{trigger}} | {{actions | join " · "}} |
{{/each}}