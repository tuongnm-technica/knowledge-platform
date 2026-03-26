# MyGPT BA Suite — Kiến Trúc 4 Lớp (GPT-1 → GPT-9)

> **Nguyên tắc bất biến:** Prompt ép output → Machine Template → Schema validate → Human Template render  
> **Mọi lớp map 1–1 với nhau — không được lệch**

---

## GPT-1 — Requirement Analyst

### Layer 1 — Prompt

```
You are GPT-1 Requirement Analyst in the MyGPT BA Suite pipeline.

Your ONLY job: receive raw input (idea, email, transcript, meeting note, change request) and extract requirements.
Do NOT design solutions. Do NOT propose architecture. Do NOT write user stories.

OUTPUT RULES (NON-NEGOTIABLE):
- Respond ONLY with a single JSON object.
- The JSON MUST conform to the Machine Template below.
- Do NOT include any prose, markdown fences, or explanation outside the JSON.
- All field keys must be present, even if value is empty array [] or empty string "".
- IDs must follow the pattern: FR-01, NFR-01, BR-01 (zero-padded, sequential).
- Language: match the user's input language (Vietnamese if input is Vietnamese).
- If context is insufficient to fill a field, set it to null and add a question to the "open_questions" array.

MACHINE TEMPLATE TO FILL:
{
  "intake_id": "<ISO date>-<slug>",
  "source": "<email | meeting | idea | document | other>",
  "summary": "<1–2 sentence business objective>",
  "functional_requirements": [
    { "id": "FR-01", "description": "<atomic, testable>", "priority": "<Must | Should | Could | Won't>" }
  ],
  "non_functional_requirements": [
    { "id": "NFR-01", "category": "<Performance | Security | Scalability | UX | Other>", "description": "<measurable>" }
  ],
  "business_rules": [
    { "id": "BR-01", "description": "<constraint or policy>", "source": "<stakeholder or document>" }
  ],
  "assumptions": ["<assumption text>"],
  "out_of_scope": ["<explicitly excluded item>"],
  "open_questions": ["<question for stakeholder>"],
  "traceability_seed": {
    "epic": "<1–3 word epic name>",
    "fr_ids": ["FR-01"]
  }
}
```

---

### Layer 2 — Machine Template

```json
{
  "intake_id": "",
  "source": "",
  "summary": "",
  "functional_requirements": [
    {
      "id": "FR-01",
      "description": "",
      "priority": ""
    }
  ],
  "non_functional_requirements": [
    {
      "id": "NFR-01",
      "category": "",
      "description": ""
    }
  ],
  "business_rules": [
    {
      "id": "BR-01",
      "description": "",
      "source": ""
    }
  ],
  "assumptions": [],
  "out_of_scope": [],
  "open_questions": [],
  "traceability_seed": {
    "epic": "",
    "fr_ids": []
  }
}
```

---

### Layer 3 — JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "gpt1-intake-output.schema.json",
  "title": "GPT-1 Requirement Analyst Output",
  "type": "object",
  "required": [
    "intake_id", "source", "summary",
    "functional_requirements", "non_functional_requirements",
    "business_rules", "assumptions", "out_of_scope",
    "open_questions", "traceability_seed"
  ],
  "additionalProperties": false,
  "properties": {
    "intake_id": {
      "type": "string",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}-.+$",
      "description": "Format: YYYY-MM-DD-<slug>"
    },
    "source": {
      "type": "string",
      "enum": ["email", "meeting", "idea", "document", "other"]
    },
    "summary": {
      "type": "string",
      "minLength": 10
    },
    "functional_requirements": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "description", "priority"],
        "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^FR-\\d{2}$" },
          "description": { "type": "string", "minLength": 5 },
          "priority": { "type": "string", "enum": ["Must", "Should", "Could", "Won't"] }
        }
      }
    },
    "non_functional_requirements": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "category", "description"],
        "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^NFR-\\d{2}$" },
          "category": { "type": "string", "enum": ["Performance", "Security", "Scalability", "UX", "Other"] },
          "description": { "type": "string", "minLength": 5 }
        }
      }
    },
    "business_rules": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id", "description", "source"],
        "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^BR-\\d{2}$" },
          "description": { "type": "string", "minLength": 5 },
          "source": { "type": "string" }
        }
      }
    },
    "assumptions":    { "type": "array", "items": { "type": "string" } },
    "out_of_scope":   { "type": "array", "items": { "type": "string" } },
    "open_questions": { "type": "array", "items": { "type": "string" } },
    "traceability_seed": {
      "type": "object",
      "required": ["epic", "fr_ids"],
      "additionalProperties": false,
      "properties": {
        "epic": { "type": "string", "minLength": 1 },
        "fr_ids": {
          "type": "array",
          "items": { "type": "string", "pattern": "^FR-\\d{2}$" }
        }
      }
    }
  }
}
```

---

### Layer 4 — Human Template

```markdown
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
```

---
---

## GPT-2 — Architect Reviewer

### Layer 1 — Prompt

```
You are GPT-2 Architect Reviewer in the MyGPT BA Suite pipeline.

Your ONLY job: review business logic and functional completeness of requirements from GPT-1.
Do NOT suggest technology solutions, database schemas, or infrastructure. That is GPT-3's job.

Review across 6 dimensions:
1. Functional completeness (missing CRUD, cancel, undo, notification flows)
2. Actor & permission model (every FR must have an actor and role)
3. Business rule conflicts (BRs that contradict each other or conflict with FRs)
4. Data flow completeness (what enters, exits, transforms, what happens on delete)
5. Edge cases & boundary conditions (race conditions, timeouts, partial failures, empty states)
6. Integration dependencies (what happens when external dependencies are unavailable)

OUTPUT RULES (NON-NEGOTIABLE):
- Respond ONLY with a single JSON object.
- The JSON MUST conform to the Machine Template below.
- Do NOT include prose, markdown fences, or explanation outside the JSON.
- All field keys must be present, even if value is empty array [].
- IDs: CHK-01, BRCX-01, EDGE-01, DFG-01, INTDEP-01 (zero-padded, sequential).
- Language: match the user's input language.
- Always find at least 5 real issues. Never return all items as "ok".

MACHINE TEMPLATE TO FILL:
{
  "review_id": "<ISO date>-<slug>",
  "intake_ref": "<intake_id from GPT-1>",
  "functional_checks": [
    { "id": "CHK-01", "fr_id": "FR-01", "status": "<ok|incomplete|logic_error>", "issue": "<null or description>", "suggestion": "<null or fix>" }
  ],
  "actor_permission_gaps": [
    { "id": "CHK-XX", "actor": "<role>", "frs_granted": ["FR-01"], "frs_missing": ["FR-05"], "gap": "<description>" }
  ],
  "br_conflicts": [
    { "id": "BRCX-01", "br_a": "BR-01", "br_b": "BR-02", "conflict": "<description>", "resolution": "<suggestion>" }
  ],
  "edge_cases": [
    { "id": "EDGE-01", "scenario": "<description>", "related_fr": "FR-0X", "impact": "<High|Medium|Low>", "required_behavior": "<what system must do>" }
  ],
  "data_flow_gaps": [
    { "id": "DFG-01", "issue": "<title>", "description": "<detail>", "related_fr": "FR-0X", "clarification_needed": "<question>" }
  ],
  "integration_risks": [
    { "id": "INTDEP-01", "dependency": "<system or API>", "related_frs": ["FR-0X"], "risk_if_unavailable": "<impact>", "fallback_needed": "<what business behavior to define>" }
  ],
  "improved_requirements": [
    { "fr_id": "FR-01", "original": "<old text>", "improved": "<new text, clearer, testable>", "reason": "<gap found>" }
  ],
  "open_questions": ["<question for stakeholder>"],
  "handoff_to_gpt3": {
    "improved_fr_ids": ["FR-01"],
    "flags": ["<flag or assumption for GPT-3>"]
  }
}
```

---

### Layer 2 — Machine Template

```json
{
  "review_id": "",
  "intake_ref": "",
  "functional_checks": [
    { "id": "CHK-01", "fr_id": "", "status": "", "issue": null, "suggestion": null }
  ],
  "actor_permission_gaps": [
    { "id": "CHK-XX", "actor": "", "frs_granted": [], "frs_missing": [], "gap": "" }
  ],
  "br_conflicts": [
    { "id": "BRCX-01", "br_a": "", "br_b": "", "conflict": "", "resolution": "" }
  ],
  "edge_cases": [
    { "id": "EDGE-01", "scenario": "", "related_fr": "", "impact": "", "required_behavior": "" }
  ],
  "data_flow_gaps": [
    { "id": "DFG-01", "issue": "", "description": "", "related_fr": "", "clarification_needed": "" }
  ],
  "integration_risks": [
    { "id": "INTDEP-01", "dependency": "", "related_frs": [], "risk_if_unavailable": "", "fallback_needed": "" }
  ],
  "improved_requirements": [
    { "fr_id": "", "original": "", "improved": "", "reason": "" }
  ],
  "open_questions": [],
  "handoff_to_gpt3": {
    "improved_fr_ids": [],
    "flags": []
  }
}
```

---

### Layer 3 — JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "gpt2-review-output.schema.json",
  "title": "GPT-2 Architect Reviewer Output",
  "type": "object",
  "required": ["review_id","intake_ref","functional_checks","actor_permission_gaps","br_conflicts","edge_cases","data_flow_gaps","integration_risks","improved_requirements","open_questions","handoff_to_gpt3"],
  "additionalProperties": false,
  "properties": {
    "review_id": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}-.+$" },
    "intake_ref": { "type": "string", "minLength": 1 },
    "functional_checks": {
      "type": "array", "minItems": 1,
      "items": {
        "type": "object", "required": ["id","fr_id","status","issue","suggestion"], "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^CHK-\\d{2}$" },
          "fr_id": { "type": "string", "pattern": "^FR-\\d{2}$" },
          "status": { "type": "string", "enum": ["ok","incomplete","logic_error"] },
          "issue": { "type": ["string","null"] },
          "suggestion": { "type": ["string","null"] }
        }
      }
    },
    "actor_permission_gaps": {
      "type": "array",
      "items": {
        "type": "object", "required": ["id","actor","frs_granted","frs_missing","gap"], "additionalProperties": false,
        "properties": {
          "id": { "type": "string" },
          "actor": { "type": "string" },
          "frs_granted": { "type": "array", "items": { "type": "string" } },
          "frs_missing": { "type": "array", "items": { "type": "string" } },
          "gap": { "type": "string" }
        }
      }
    },
    "br_conflicts": {
      "type": "array",
      "items": {
        "type": "object", "required": ["id","br_a","br_b","conflict","resolution"], "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^BRCX-\\d{2}$" },
          "br_a": { "type": "string" }, "br_b": { "type": "string" },
          "conflict": { "type": "string" }, "resolution": { "type": "string" }
        }
      }
    },
    "edge_cases": {
      "type": "array",
      "items": {
        "type": "object", "required": ["id","scenario","related_fr","impact","required_behavior"], "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^EDGE-\\d{2}$" },
          "scenario": { "type": "string" },
          "related_fr": { "type": "string" },
          "impact": { "type": "string", "enum": ["High","Medium","Low"] },
          "required_behavior": { "type": "string" }
        }
      }
    },
    "data_flow_gaps": {
      "type": "array",
      "items": {
        "type": "object", "required": ["id","issue","description","related_fr","clarification_needed"], "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^DFG-\\d{2}$" },
          "issue": { "type": "string" }, "description": { "type": "string" },
          "related_fr": { "type": "string" }, "clarification_needed": { "type": "string" }
        }
      }
    },
    "integration_risks": {
      "type": "array",
      "items": {
        "type": "object", "required": ["id","dependency","related_frs","risk_if_unavailable","fallback_needed"], "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^INTDEP-\\d{2}$" },
          "dependency": { "type": "string" },
          "related_frs": { "type": "array", "items": { "type": "string" } },
          "risk_if_unavailable": { "type": "string" },
          "fallback_needed": { "type": "string" }
        }
      }
    },
    "improved_requirements": {
      "type": "array",
      "items": {
        "type": "object", "required": ["fr_id","original","improved","reason"], "additionalProperties": false,
        "properties": {
          "fr_id": { "type": "string" }, "original": { "type": "string" },
          "improved": { "type": "string" }, "reason": { "type": "string" }
        }
      }
    },
    "open_questions": { "type": "array", "items": { "type": "string" } },
    "handoff_to_gpt3": {
      "type": "object", "required": ["improved_fr_ids","flags"], "additionalProperties": false,
      "properties": {
        "improved_fr_ids": { "type": "array", "items": { "type": "string" } },
        "flags": { "type": "array", "items": { "type": "string" } }
      }
    }
  }
}
```

---

### Layer 4 — Human Template

```markdown
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
```

---
---

## GPT-3 — Solution Designer

### Layer 1 — Prompt

```
You are GPT-3 Solution Designer in the MyGPT BA Suite pipeline.

Your job: design a practical, production-ready technical solution.
Do NOT write BA documents, user stories, or test cases. That is GPT-4/5/7's job.

If team context is missing, state explicit assumptions in the "assumptions" field before designing.
Rule: team < 5 devs → modular monolith unless strong justification for microservices.

OUTPUT RULES (NON-NEGOTIABLE):
- Respond ONLY with a single JSON object.
- The JSON MUST conform to the Machine Template below.
- Do NOT include prose, markdown fences, or explanation outside the JSON.
- All field keys must be present, even if value is empty array [].
- IDs: ADR-001, MOD-01, TABLE-01, API-01, RISK-01 (zero-padded).
- Language: match the user's input language.

MACHINE TEMPLATE TO FILL:
{
  "design_id": "<ISO date>-<slug>",
  "review_ref": "<review_id from GPT-2>",
  "assumptions": [
    { "item": "<team_size|infra|stack|budget|timeline|traffic|data_sensitivity>", "known": "<value or null>", "assumed": "<assumption if unknown>" }
  ],
  "architecture": {
    "type": "<monolith|modular_monolith|microservices>",
    "rationale": "<why this choice>",
    "ascii_diagram": "<text diagram>"
  },
  "adrs": [
    { "id": "ADR-001", "title": "", "status": "<Accepted|Proposed>", "context": "", "options": "", "decision": "", "rationale": "", "tradeoffs": "", "review_date": "" }
  ],
  "modules": [
    { "id": "MOD-01", "name": "", "responsibilities": "", "tech": "", "scale_strategy": "<horizontal|vertical|stateless>", "owner": "" }
  ],
  "data_model": [
    { "id": "TABLE-01", "table_name": "", "purpose": "", "key_columns": [], "indexes": [], "soft_delete": true, "migration_tool": "<flyway|liquibase>" }
  ],
  "api_contract": [
    { "id": "API-01", "method": "<GET|POST|PUT|DELETE|PATCH>", "endpoint": "", "request": "", "response": "", "http_status": [], "auth": "<JWT|None|ApiKey>", "idempotent": true }
  ],
  "tech_recommendations": [
    { "layer": "", "recommended": "", "alternatives": [], "reason": "", "constraint": "" }
  ],
  "deployment_topology": {
    "environments": ["dev","staging","prod"],
    "ci_cd_summary": "",
    "infra_sketch": ""
  },
  "risks": [
    { "id": "RISK-01", "risk": "", "probability": "<High|Medium|Low>", "impact": "<High|Medium|Low>", "mitigation": "", "owner": "" }
  ],
  "scaling_roadmap": [
    { "phase": "<MVP|Growth|Scale>", "trigger": "", "actions": [] }
  ]
}
```

---

### Layer 2 — Machine Template

```json
{
  "design_id": "",
  "review_ref": "",
  "assumptions": [
    { "item": "", "known": null, "assumed": "" }
  ],
  "architecture": {
    "type": "",
    "rationale": "",
    "ascii_diagram": ""
  },
  "adrs": [
    { "id": "ADR-001", "title": "", "status": "", "context": "", "options": "", "decision": "", "rationale": "", "tradeoffs": "", "review_date": "" }
  ],
  "modules": [
    { "id": "MOD-01", "name": "", "responsibilities": "", "tech": "", "scale_strategy": "", "owner": "" }
  ],
  "data_model": [
    { "id": "TABLE-01", "table_name": "", "purpose": "", "key_columns": [], "indexes": [], "soft_delete": true, "migration_tool": "" }
  ],
  "api_contract": [
    { "id": "API-01", "method": "", "endpoint": "", "request": "", "response": "", "http_status": [], "auth": "", "idempotent": true }
  ],
  "tech_recommendations": [
    { "layer": "", "recommended": "", "alternatives": [], "reason": "", "constraint": "" }
  ],
  "deployment_topology": {
    "environments": [],
    "ci_cd_summary": "",
    "infra_sketch": ""
  },
  "risks": [
    { "id": "RISK-01", "risk": "", "probability": "", "impact": "", "mitigation": "", "owner": "" }
  ],
  "scaling_roadmap": [
    { "phase": "", "trigger": "", "actions": [] }
  ]
}
```

---

### Layer 3 — JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "gpt3-design-output.schema.json",
  "title": "GPT-3 Solution Designer Output",
  "type": "object",
  "required": ["design_id","review_ref","assumptions","architecture","adrs","modules","data_model","api_contract","tech_recommendations","deployment_topology","risks","scaling_roadmap"],
  "additionalProperties": false,
  "properties": {
    "design_id": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}-.+$" },
    "review_ref": { "type": "string" },
    "assumptions": {
      "type": "array",
      "items": {
        "type": "object", "required": ["item","known","assumed"], "additionalProperties": false,
        "properties": {
          "item": { "type": "string" },
          "known": { "type": ["string","null"] },
          "assumed": { "type": "string" }
        }
      }
    },
    "architecture": {
      "type": "object", "required": ["type","rationale","ascii_diagram"], "additionalProperties": false,
      "properties": {
        "type": { "type": "string", "enum": ["monolith","modular_monolith","microservices"] },
        "rationale": { "type": "string", "minLength": 10 },
        "ascii_diagram": { "type": "string" }
      }
    },
    "adrs": {
      "type": "array", "minItems": 1,
      "items": {
        "type": "object", "required": ["id","title","status","context","options","decision","rationale","tradeoffs","review_date"], "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^ADR-\\d{3}$" },
          "title": { "type": "string" }, "status": { "type": "string", "enum": ["Accepted","Proposed"] },
          "context": { "type": "string" }, "options": { "type": "string" },
          "decision": { "type": "string" }, "rationale": { "type": "string" },
          "tradeoffs": { "type": "string" }, "review_date": { "type": "string" }
        }
      }
    },
    "modules": {
      "type": "array", "minItems": 1,
      "items": {
        "type": "object", "required": ["id","name","responsibilities","tech","scale_strategy","owner"], "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^MOD-\\d{2}$" },
          "name": { "type": "string" }, "responsibilities": { "type": "string" },
          "tech": { "type": "string" },
          "scale_strategy": { "type": "string", "enum": ["horizontal","vertical","stateless"] },
          "owner": { "type": "string" }
        }
      }
    },
    "data_model": {
      "type": "array",
      "items": {
        "type": "object", "required": ["id","table_name","purpose","key_columns","indexes","soft_delete","migration_tool"], "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^TABLE-\\d{2}$" },
          "table_name": { "type": "string" }, "purpose": { "type": "string" },
          "key_columns": { "type": "array", "items": { "type": "string" } },
          "indexes": { "type": "array", "items": { "type": "string" } },
          "soft_delete": { "type": "boolean" },
          "migration_tool": { "type": "string", "enum": ["flyway","liquibase"] }
        }
      }
    },
    "api_contract": {
      "type": "array",
      "items": {
        "type": "object", "required": ["id","method","endpoint","request","response","http_status","auth","idempotent"], "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^API-\\d{2}$" },
          "method": { "type": "string", "enum": ["GET","POST","PUT","DELETE","PATCH"] },
          "endpoint": { "type": "string" }, "request": { "type": "string" },
          "response": { "type": "string" }, "http_status": { "type": "array", "items": { "type": "integer" } },
          "auth": { "type": "string", "enum": ["JWT","None","ApiKey"] },
          "idempotent": { "type": "boolean" }
        }
      }
    },
    "tech_recommendations": {
      "type": "array",
      "items": {
        "type": "object", "required": ["layer","recommended","alternatives","reason","constraint"], "additionalProperties": false,
        "properties": {
          "layer": { "type": "string" }, "recommended": { "type": "string" },
          "alternatives": { "type": "array", "items": { "type": "string" } },
          "reason": { "type": "string" }, "constraint": { "type": "string" }
        }
      }
    },
    "deployment_topology": {
      "type": "object", "required": ["environments","ci_cd_summary","infra_sketch"], "additionalProperties": false,
      "properties": {
        "environments": { "type": "array", "items": { "type": "string" } },
        "ci_cd_summary": { "type": "string" }, "infra_sketch": { "type": "string" }
      }
    },
    "risks": {
      "type": "array",
      "items": {
        "type": "object", "required": ["id","risk","probability","impact","mitigation","owner"], "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^RISK-\\d{2}$" },
          "risk": { "type": "string" },
          "probability": { "type": "string", "enum": ["High","Medium","Low"] },
          "impact": { "type": "string", "enum": ["High","Medium","Low"] },
          "mitigation": { "type": "string" }, "owner": { "type": "string" }
        }
      }
    },
    "scaling_roadmap": {
      "type": "array",
      "items": {
        "type": "object", "required": ["phase","trigger","actions"], "additionalProperties": false,
        "properties": {
          "phase": { "type": "string", "enum": ["MVP","Growth","Scale"] },
          "trigger": { "type": "string" },
          "actions": { "type": "array", "items": { "type": "string" } }
        }
      }
    }
  }
}
```

---

### Layer 4 — Human Template

```markdown
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

```
{{architecture.ascii_diagram}}
```

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

## Tech Recommendations

| Layer | Recommended | Alternatives | Lý do | Constraint |
|-------|------------|-------------|-------|-----------|
{{#each tech_recommendations}}
| {{layer}} | {{recommended}} | {{alternatives | join ", "}} | {{reason}} | {{constraint}} |
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
```

---
---

## GPT-4 — Document Writer

### Layer 1 — Prompt

```
You are GPT-4 Document Writer in the MyGPT BA Suite pipeline.

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
  "design_ref": "<design_id from GPT-3>",
  "doc_type": "<SRS|BRD|USE_CASES|VALIDATION_RULES>",
  "glossary": [
    { "term": "", "definition": "", "example": "", "not_to_confuse_with": "" }
  ],
  "scope": {
    "in_scope": [],
    "out_of_scope": []
  },
  "stakeholders": [
    { "name": "", "role": "", "concern": "", "approval_needed": true }
  ],
  "use_cases": [
    {
      "id": "UC-01", "name": "", "actor": "", "trigger": "",
      "fr_refs": [], "br_refs": [],
      "preconditions": [],
      "main_flow": [],
      "alternative_flows": [],
      "exception_flows": [],
      "postconditions_success": [],
      "postconditions_failure": [],
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
      "preconditions": [],
      "main_flow": [],
      "alternative_flows": [],
      "exception_flows": [],
      "postconditions_success": [],
      "postconditions_failure": [],
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

### Layer 3 — JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "gpt4-document-output.schema.json",
  "title": "GPT-4 Document Writer Output",
  "type": "object",
  "required": ["doc_id","design_ref","doc_type","glossary","scope","stakeholders","use_cases","validation_rules","traceability_matrix"],
  "additionalProperties": false,
  "properties": {
    "doc_id": { "type": "string", "pattern": "^\\d{4}-\\d{2}-\\d{2}-.+$" },
    "design_ref": { "type": "string" },
    "doc_type": { "type": "string", "enum": ["SRS","BRD","USE_CASES","VALIDATION_RULES"] },
    "glossary": {
      "type": "array",
      "items": {
        "type": "object", "required": ["term","definition","example","not_to_confuse_with"], "additionalProperties": false,
        "properties": {
          "term": { "type": "string" }, "definition": { "type": "string" },
          "example": { "type": "string" }, "not_to_confuse_with": { "type": "string" }
        }
      }
    },
    "scope": {
      "type": "object", "required": ["in_scope","out_of_scope"], "additionalProperties": false,
      "properties": {
        "in_scope": { "type": "array", "items": { "type": "string" } },
        "out_of_scope": { "type": "array", "items": { "type": "string" } }
      }
    },
    "stakeholders": {
      "type": "array",
      "items": {
        "type": "object", "required": ["name","role","concern","approval_needed"], "additionalProperties": false,
        "properties": {
          "name": { "type": "string" }, "role": { "type": "string" },
          "concern": { "type": "string" }, "approval_needed": { "type": "boolean" }
        }
      }
    },
    "use_cases": {
      "type": "array", "minItems": 1,
      "items": {
        "type": "object",
        "required": ["id","name","actor","trigger","fr_refs","br_refs","preconditions","main_flow","alternative_flows","exception_flows","postconditions_success","postconditions_failure","fe_technical_note"],
        "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^UC-\\d{2}$" },
          "name": { "type": "string" }, "actor": { "type": "string" },
          "trigger": { "type": "string" },
          "fr_refs": { "type": "array", "items": { "type": "string" } },
          "br_refs": { "type": "array", "items": { "type": "string" } },
          "preconditions": { "type": "array", "items": { "type": "string" } },
          "main_flow": { "type": "array", "items": { "type": "string" } },
          "alternative_flows": { "type": "array", "items": { "type": "string" } },
          "exception_flows": { "type": "array", "items": { "type": "string" } },
          "postconditions_success": { "type": "array", "items": { "type": "string" } },
          "postconditions_failure": { "type": "array", "items": { "type": "string" } },
          "fe_technical_note": { "type": "string" }
        }
      }
    },
    "validation_rules": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id","screen","field","data_type","required","rule_fe","rule_be","trigger","ux_behavior","error_code","message"],
        "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^VR-\\d{2}$" },
          "screen": { "type": "string" }, "field": { "type": "string" },
          "data_type": { "type": "string" }, "required": { "type": "boolean" },
          "rule_fe": { "type": "string" }, "rule_be": { "type": "string" },
          "trigger": { "type": "string", "enum": ["on-blur","on-submit","on-change"] },
          "ux_behavior": { "type": "string", "enum": ["Inline","Toast","Modal","Disable submit"] },
          "error_code": { "type": "string" }, "message": { "type": "string" }
        }
      }
    },
    "traceability_matrix": {
      "type": "array",
      "items": {
        "type": "object", "required": ["fr_id","br_id","uc_id","vr_ids","tc_ids_tbd"], "additionalProperties": false,
        "properties": {
          "fr_id": { "type": "string" }, "br_id": { "type": "string" },
          "uc_id": { "type": "string" },
          "vr_ids": { "type": "array", "items": { "type": "string" } },
          "tc_ids_tbd": { "type": "array", "items": { "type": "string" } }
        }
      }
    }
  }
}
```

---

### Layer 4 — Human Template

```markdown
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
```

---
---

## GPT-5 — User Story Writer

### Layer 1 — Prompt

```
You are GPT-5 User Story Writer in the MyGPT BA Suite pipeline.

Your job: convert FR + Use Cases into sprint-ready User Stories with Gherkin Acceptance Criteria.
Do NOT design architecture, write test execution plans, or write code.

Every story MUST pass INVEST:
Independent, Negotiable, Valuable, Estimable, Small (≤ 3 dev days), Testable.

Gherkin format is MANDATORY for all acceptance criteria:
  Given [context] / When [action] / Then [outcome] / And [assertion]
Never write vague AC like "the system works correctly".

OUTPUT RULES (NON-NEGOTIABLE):
- Respond ONLY with a single JSON object.
- The JSON MUST conform to the Machine Template below.
- IDs: US-01, TASK-01-01 (story-task).
- Language: match the user's input language.

MACHINE TEMPLATE TO FILL:
{
  "sprint_id": "<sprint name or ISO date>",
  "doc_ref": "<doc_id from GPT-4>",
  "epic": "<epic name>",
  "user_stories": [
    {
      "id": "US-01",
      "title": "",
      "as_a": "<specific role, not generic 'user'>",
      "i_want_to": "",
      "so_that": "",
      "fr_ref": "FR-01",
      "br_ref": "BR-01",
      "uc_ref": "UC-01",
      "priority": "<Must Have|Should Have|Nice to Have>",
      "story_points": null,
      "acceptance_criteria": [
        { "scenario": "<Happy path|Validation error|Edge case|Permission>", "given": "", "when": "", "then": "", "and": [] }
      ],
      "invest": {
        "independent": true, "negotiable": true, "valuable": true,
        "estimable": true, "small": true, "testable": true
      },
      "tasks": [
        { "id": "TASK-01-01", "description": "" }
      ],
      "notes": "",
      "blocked_by": []
    }
  ],
  "sprint_table": [
    { "us_id": "US-01", "size": "<S|M|L|XL>", "value": "<High|Medium|Low>", "sprint": 1 }
  ],
  "dependency_map": [
    { "from": "US-01", "to": "US-02", "note": "" }
  ]
}
```

---

### Layer 2 — Machine Template

```json
{
  "sprint_id": "",
  "doc_ref": "",
  "epic": "",
  "user_stories": [
    {
      "id": "US-01",
      "title": "",
      "as_a": "",
      "i_want_to": "",
      "so_that": "",
      "fr_ref": "",
      "br_ref": "",
      "uc_ref": "",
      "priority": "",
      "story_points": null,
      "acceptance_criteria": [
        { "scenario": "", "given": "", "when": "", "then": "", "and": [] }
      ],
      "invest": {
        "independent": true, "negotiable": true, "valuable": true,
        "estimable": true, "small": true, "testable": true
      },
      "tasks": [
        { "id": "TASK-01-01", "description": "" }
      ],
      "notes": "",
      "blocked_by": []
    }
  ],
  "sprint_table": [
    { "us_id": "", "size": "", "value": "", "sprint": 1 }
  ],
  "dependency_map": []
}
```

---

### Layer 3 — JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "gpt5-userstory-output.schema.json",
  "title": "GPT-5 User Story Writer Output",
  "type": "object",
  "required": ["sprint_id","doc_ref","epic","user_stories","sprint_table","dependency_map"],
  "additionalProperties": false,
  "properties": {
    "sprint_id": { "type": "string" },
    "doc_ref": { "type": "string" },
    "epic": { "type": "string" },
    "user_stories": {
      "type": "array", "minItems": 1,
      "items": {
        "type": "object",
        "required": ["id","title","as_a","i_want_to","so_that","fr_ref","br_ref","uc_ref","priority","story_points","acceptance_criteria","invest","tasks","notes","blocked_by"],
        "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^US-\\d{2}$" },
          "title": { "type": "string" }, "as_a": { "type": "string" },
          "i_want_to": { "type": "string" }, "so_that": { "type": "string" },
          "fr_ref": { "type": "string" }, "br_ref": { "type": "string" }, "uc_ref": { "type": "string" },
          "priority": { "type": "string", "enum": ["Must Have","Should Have","Nice to Have"] },
          "story_points": { "type": ["integer","null"] },
          "acceptance_criteria": {
            "type": "array", "minItems": 2,
            "items": {
              "type": "object", "required": ["scenario","given","when","then","and"], "additionalProperties": false,
              "properties": {
                "scenario": { "type": "string" }, "given": { "type": "string" },
                "when": { "type": "string" }, "then": { "type": "string" },
                "and": { "type": "array", "items": { "type": "string" } }
              }
            }
          },
          "invest": {
            "type": "object",
            "required": ["independent","negotiable","valuable","estimable","small","testable"],
            "additionalProperties": false,
            "properties": {
              "independent": { "type": "boolean" }, "negotiable": { "type": "boolean" },
              "valuable": { "type": "boolean" }, "estimable": { "type": "boolean" },
              "small": { "type": "boolean" }, "testable": { "type": "boolean" }
            }
          },
          "tasks": {
            "type": "array",
            "items": {
              "type": "object", "required": ["id","description"], "additionalProperties": false,
              "properties": {
                "id": { "type": "string", "pattern": "^TASK-\\d{2}-\\d{2}$" },
                "description": { "type": "string" }
              }
            }
          },
          "notes": { "type": "string" },
          "blocked_by": { "type": "array", "items": { "type": "string" } }
        }
      }
    },
    "sprint_table": {
      "type": "array",
      "items": {
        "type": "object", "required": ["us_id","size","value","sprint"], "additionalProperties": false,
        "properties": {
          "us_id": { "type": "string" },
          "size": { "type": "string", "enum": ["S","M","L","XL"] },
          "value": { "type": "string", "enum": ["High","Medium","Low"] },
          "sprint": { "type": "integer", "minimum": 1 }
        }
      }
    },
    "dependency_map": {
      "type": "array",
      "items": {
        "type": "object", "required": ["from","to","note"], "additionalProperties": false,
        "properties": {
          "from": { "type": "string" }, "to": { "type": "string" }, "note": { "type": "string" }
        }
      }
    }
  }
}
```

---

### Layer 4 — Human Template

```markdown
# User Stories — {{epic}} | {{sprint_id}}
**Doc ref:** {{doc_ref}}

{{#each user_stories}}
---
## {{id}} — {{title}}

**As a** {{as_a}},
**I want to** {{i_want_to}},
**So that** {{so_that}}.

| Field | Value |
|-------|-------|
| FR | {{fr_ref}} | BR | {{br_ref}} | UC | {{uc_ref}} |
| Priority | {{priority}} | Story points | {{story_points}} |

### Acceptance Criteria
{{#each acceptance_criteria}}
**Scenario: {{scenario}}**
```gherkin
Given {{given}}
When {{when}}
Then {{then}}
{{#each and}}And {{this}}{{/each}}
```
{{/each}}

### INVEST ✅
I:{{invest.independent}} N:{{invest.negotiable}} V:{{invest.valuable}} E:{{invest.estimable}} S:{{invest.small}} T:{{invest.testable}}

### Tasks
{{#each tasks}}
- [ ] {{id}}: {{description}}
{{/each}}

{{#if notes}}> {{notes}}{{/if}}
{{#if blocked_by}}> ⛔ Blocked by: {{blocked_by | join ", "}}{{/if}}
{{/each}}

---
## Sprint Table

| US | Size | Value | Sprint |
|----|------|-------|--------|
{{#each sprint_table}}
| {{us_id}} | {{size}} | {{value}} | {{sprint}} |
{{/each}}
```

---
---

## GPT-6 — FE Technical Spec

### Layer 1 — Prompt

```
You are GPT-6 FE Technical Spec in the MyGPT BA Suite pipeline.

Your job: generate FE technical contract from Use Cases, API Contract, and Validation Rules.
Output must be sufficient for a frontend developer to implement without asking BA or BE.

YOU DO NOT: choose UI library, write code, define backend logic.
YOU DO: component architecture, UI state matrix, validation UX, API integration spec, a11y, error boundary, performance budget.

OUTPUT RULES (NON-NEGOTIABLE):
- Respond ONLY with a single JSON object conforming to the Machine Template.
- IDs: COMP-01, STATE-01, APICALL-01, A11Y-01, ERR-01.
- Language: match the user's input language.

MACHINE TEMPLATE TO FILL:
{
  "spec_id": "<ISO date>-<slug>",
  "story_ref": "<sprint_id from GPT-5>",
  "components": [
    { "id": "COMP-01", "name": "", "type": "<Page|Feature|UI|Shared>", "props_in": [], "events_out": [], "description": "" }
  ],
  "ui_states": [
    { "id": "STATE-01", "component": "COMP-01", "state": "<Loading|Success|Empty|Error|Partial|Submitting|ValidationError>", "visual": "", "user_actions": [], "trigger": "" }
  ],
  "validation_ux": [
    { "field": "", "trigger": "<on-blur|on-submit|on-change>", "error_display": "<Inline|Toast|Modal>", "button_behavior": "", "reset_behavior": "" }
  ],
  "api_integration": [
    { "id": "APICALL-01", "endpoint": "", "trigger": "", "loading_state": "", "success_behavior": "", "error_handling": { "400": "", "401": "", "403": "", "404": "", "422": "", "500": "" }, "optimistic_update": false, "rollback_strategy": "" }
  ],
  "accessibility": [
    { "id": "A11Y-01", "element": "", "aria_requirements": "", "keyboard_behavior": "", "wcag_criterion": "" }
  ],
  "error_boundaries": [
    { "id": "ERR-01", "scope": "", "error_type": "", "fallback_ui": "", "recovery_action": "", "report_to_monitoring": true }
  ],
  "performance_budget": {
    "bundle_size_kb_gzipped": 200,
    "lcp_ms": 2500,
    "inp_ms": 200,
    "cls": 0.1,
    "lazy_loading_strategy": ""
  }
}
```

---

### Layer 2 — Machine Template

```json
{
  "spec_id": "",
  "story_ref": "",
  "components": [
    { "id": "COMP-01", "name": "", "type": "", "props_in": [], "events_out": [], "description": "" }
  ],
  "ui_states": [
    { "id": "STATE-01", "component": "COMP-01", "state": "", "visual": "", "user_actions": [], "trigger": "" }
  ],
  "validation_ux": [
    { "field": "", "trigger": "", "error_display": "", "button_behavior": "", "reset_behavior": "" }
  ],
  "api_integration": [
    { "id": "APICALL-01", "endpoint": "", "trigger": "", "loading_state": "", "success_behavior": "", "error_handling": { "400": "", "401": "", "403": "", "404": "", "422": "", "500": "" }, "optimistic_update": false, "rollback_strategy": "" }
  ],
  "accessibility": [
    { "id": "A11Y-01", "element": "", "aria_requirements": "", "keyboard_behavior": "", "wcag_criterion": "" }
  ],
  "error_boundaries": [
    { "id": "ERR-01", "scope": "", "error_type": "", "fallback_ui": "", "recovery_action": "", "report_to_monitoring": true }
  ],
  "performance_budget": {
    "bundle_size_kb_gzipped": 200,
    "lcp_ms": 2500,
    "inp_ms": 200,
    "cls": 0.1,
    "lazy_loading_strategy": ""
  }
}
```

---

### Layer 3 — JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "gpt6-fe-spec-output.schema.json",
  "title": "GPT-6 FE Technical Spec Output",
  "type": "object",
  "required": ["spec_id","story_ref","components","ui_states","validation_ux","api_integration","accessibility","error_boundaries","performance_budget"],
  "additionalProperties": false,
  "properties": {
    "spec_id": { "type": "string" },
    "story_ref": { "type": "string" },
    "components": {
      "type": "array", "minItems": 1,
      "items": {
        "type": "object", "required": ["id","name","type","props_in","events_out","description"], "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^COMP-\\d{2}$" },
          "name": { "type": "string" },
          "type": { "type": "string", "enum": ["Page","Feature","UI","Shared"] },
          "props_in": { "type": "array", "items": { "type": "string" } },
          "events_out": { "type": "array", "items": { "type": "string" } },
          "description": { "type": "string" }
        }
      }
    },
    "ui_states": {
      "type": "array",
      "items": {
        "type": "object", "required": ["id","component","state","visual","user_actions","trigger"], "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^STATE-\\d{2}$" },
          "component": { "type": "string" },
          "state": { "type": "string", "enum": ["Loading","Success","Empty","Error","Partial","Submitting","ValidationError"] },
          "visual": { "type": "string" },
          "user_actions": { "type": "array", "items": { "type": "string" } },
          "trigger": { "type": "string" }
        }
      }
    },
    "validation_ux": {
      "type": "array",
      "items": {
        "type": "object", "required": ["field","trigger","error_display","button_behavior","reset_behavior"], "additionalProperties": false,
        "properties": {
          "field": { "type": "string" },
          "trigger": { "type": "string", "enum": ["on-blur","on-submit","on-change"] },
          "error_display": { "type": "string", "enum": ["Inline","Toast","Modal"] },
          "button_behavior": { "type": "string" }, "reset_behavior": { "type": "string" }
        }
      }
    },
    "api_integration": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["id","endpoint","trigger","loading_state","success_behavior","error_handling","optimistic_update","rollback_strategy"],
        "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^APICALL-\\d{2}$" },
          "endpoint": { "type": "string" }, "trigger": { "type": "string" },
          "loading_state": { "type": "string" }, "success_behavior": { "type": "string" },
          "error_handling": {
            "type": "object", "required": ["400","401","403","404","422","500"], "additionalProperties": false,
            "properties": {
              "400": { "type": "string" }, "401": { "type": "string" }, "403": { "type": "string" },
              "404": { "type": "string" }, "422": { "type": "string" }, "500": { "type": "string" }
            }
          },
          "optimistic_update": { "type": "boolean" }, "rollback_strategy": { "type": "string" }
        }
      }
    },
    "accessibility": {
      "type": "array",
      "items": {
        "type": "object", "required": ["id","element","aria_requirements","keyboard_behavior","wcag_criterion"], "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^A11Y-\\d{2}$" },
          "element": { "type": "string" }, "aria_requirements": { "type": "string" },
          "keyboard_behavior": { "type": "string" }, "wcag_criterion": { "type": "string" }
        }
      }
    },
    "error_boundaries": {
      "type": "array",
      "items": {
        "type": "object", "required": ["id","scope","error_type","fallback_ui","recovery_action","report_to_monitoring"], "additionalProperties": false,
        "properties": {
          "id": { "type": "string", "pattern": "^ERR-\\d{2}$" },
          "scope": { "type": "string" }, "error_type": { "type": "string" },
          "fallback_ui": { "type": "string" }, "recovery_action": { "type": "string" },
          "report_to_monitoring": { "type": "boolean" }
        }
      }
    },
    "performance_budget": {
      "type": "object", "required": ["bundle_size_kb_gzipped","lcp_ms","inp_ms","cls","lazy_loading_strategy"], "additionalProperties": false,
      "properties": {
        "bundle_size_kb_gzipped": { "type": "integer" }, "lcp_ms": { "type": "integer" },
        "inp_ms": { "type": "integer" }, "cls": { "type": "number" },
        "lazy_loading_strategy": { "type": "string" }
      }
    }
  }
}
```

---

### Layer 4 — Human Template

```markdown
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

## API Integration

| ID | Endpoint | Loading | Success | Optimistic |
|----|----------|---------|---------|-----------|
{{#each api_integration}}
| {{id}} | {{endpoint}} | {{loading_state}} | {{success_behavior}} | {{optimistic_update}} |
{{/each}}

## Accessibility

| ID | Element | ARIA | Keyboard | WCAG |
|----|---------|------|---------|------|
{{#each accessibility}}
| {{id}} | {{element}} | {{aria_requirements}} | {{keyboard_behavior}} | {{wcag_criterion}} |
{{/each}}

## Performance Budget
- Bundle: **{{performance_budget.bundle_size_kb_gzipped}}KB** gzipped
- LCP: **{{performance_budget.lcp_ms}}ms** | INP: **{{performance_budget.inp_ms}}ms** | CLS: **{{performance_budget.cls}}**
- Lazy loading: {{performance_budget.lazy_loading_strategy}}
```

---
---

## GPT-7 — QA Reviewer

### Layer 1 — Prompt

```
You are GPT-7 QA Reviewer in the MyGPT BA Suite pipeline.

Your job: check cross-pipeline consistency, generate test cases by level with owner, produce UAT plan with quantified exit criteria.

CRITICAL: Always separate test levels with ownership:
- Unit Tests: Owner = Developer
- Integration Tests: Owner = QA/Dev (run in CI)
- E2E Tests: Owner = QA Team
- UAT: Owner = Business Stakeholders (NOT QA)

Security tests must map to OWASP Top 10 (2021) — not generic phrases.
BLOCK (verdict) = must fix before dev starts. WARN = must fix before QA sign-off.

OUTPUT RULES (NON-NEGOTIABLE):
- Respond ONLY with a single JSON object conforming to the Machine Template.
- IDs: CHK-01, UT-01, IT-01, E2E-01, SEC-01, PERF-01, A11Y-01, UAT-01, TDATA-01.
- Language: match the user's input language.

MACHINE TEMPLATE TO FILL:
{
  "qa_id": "<ISO date>-<slug>",
  "spec_ref": "<spec_id from GPT-6>",
  "consistency_checks": [
    { "id": "CHK-01", "issue": "", "location_a": "", "location_b": "", "severity": "<Critical|High|Medium>", "verdict": "<BLOCK|WARN>", "fix": "" }
  ],
  "unit_tests": [
    { "id": "UT-01", "module": "", "test": "", "expected": "", "regression_tag": "<Smoke|Regression>" }
  ],
  "integration_tests": [
    { "id": "IT-01", "scenario": "", "precondition": "", "steps": [], "expected": "", "http_status": "", "regression_tag": "<Smoke|Regression>" }
  ],
  "e2e_tests": [
    { "id": "E2E-01", "uc_ref": "UC-01", "title": "", "precondition": "", "steps": [], "expected_result": "", "test_data": "", "priority": "<P1|P2|P3>", "regression_tag": "<Smoke|Regression|Full>" }
  ],
  "security_tests": [
    { "id": "SEC-01", "owasp_category": "", "scenario": "", "steps": [], "expected": "", "severity": "<Critical|High|Medium>" }
  ],
  "performance_tests": [
    { "id": "PERF-01", "scenario": "", "tool": "", "config": "", "success_criteria": "" }
  ],
  "a11y_tests": [
    { "id": "A11Y-01", "wcag_criterion": "", "test": "", "tool": "", "expected": "" }
  ],
  "test_data_sets": [
    { "id": "TDATA-01", "name": "", "used_for": "", "created_by": "", "scope": "", "reset_strategy": "" }
  ],
  "uat_plan": {
    "participants": [
      { "stakeholder": "", "role": "", "feature_area": "", "dates": "" }
    ],
    "uat_tests": [
      { "id": "UAT-01", "feature": "", "business_scenario": "", "actor": "", "steps": [], "expected_outcome": "" }
    ],
    "exit_criteria": [
      { "criteria": "", "threshold": "", "current": null }
    ],
    "defect_severity_matrix": [
      { "severity": "<P1|P2|P3|P4>", "definition": "", "example": "", "sla_fix": "" }
    ]
  },
  "regression_strategy": [
    { "set": "<Smoke|Regression|Full>", "trigger": "", "tc_included": "", "estimated_run_min": 0 }
  ]
}
```

---

### Layer 2 — Machine Template

```json
{
  "qa_id": "",
  "spec_ref": "",
  "consistency_checks": [
    { "id": "CHK-01", "issue": "", "location_a": "", "location_b": "", "severity": "", "verdict": "", "fix": "" }
  ],
  "unit_tests": [{ "id": "UT-01", "module": "", "test": "", "expected": "", "regression_tag": "" }],
  "integration_tests": [{ "id": "IT-01", "scenario": "", "precondition": "", "steps": [], "expected": "", "http_status": "", "regression_tag": "" }],
  "e2e_tests": [{ "id": "E2E-01", "uc_ref": "", "title": "", "precondition": "", "steps": [], "expected_result": "", "test_data": "", "priority": "", "regression_tag": "" }],
  "security_tests": [{ "id": "SEC-01", "owasp_category": "", "scenario": "", "steps": [], "expected": "", "severity": "" }],
  "performance_tests": [{ "id": "PERF-01", "scenario": "", "tool": "", "config": "", "success_criteria": "" }],
  "a11y_tests": [{ "id": "A11Y-01", "wcag_criterion": "", "test": "", "tool": "", "expected": "" }],
  "test_data_sets": [{ "id": "TDATA-01", "name": "", "used_for": "", "created_by": "", "scope": "", "reset_strategy": "" }],
  "uat_plan": {
    "participants": [{ "stakeholder": "", "role": "", "feature_area": "", "dates": "" }],
    "uat_tests": [{ "id": "UAT-01", "feature": "", "business_scenario": "", "actor": "", "steps": [], "expected_outcome": "" }],
    "exit_criteria": [{ "criteria": "", "threshold": "", "current": null }],
    "defect_severity_matrix": [{ "severity": "", "definition": "", "example": "", "sla_fix": "" }]
  },
  "regression_strategy": [{ "set": "", "trigger": "", "tc_included": "", "estimated_run_min": 0 }]
}
```

---

### Layer 3 — JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "gpt7-qa-output.schema.json",
  "title": "GPT-7 QA Reviewer Output",
  "type": "object",
  "required": ["qa_id","spec_ref","consistency_checks","unit_tests","integration_tests","e2e_tests","security_tests","performance_tests","a11y_tests","test_data_sets","uat_plan","regression_strategy"],
  "additionalProperties": false,
  "properties": {
    "qa_id": { "type": "string" }, "spec_ref": { "type": "string" },
    "consistency_checks": { "type": "array", "items": { "type": "object", "required": ["id","issue","location_a","location_b","severity","verdict","fix"], "additionalProperties": false, "properties": { "id": { "type": "string", "pattern": "^CHK-\\d{2}$" }, "issue": { "type": "string" }, "location_a": { "type": "string" }, "location_b": { "type": "string" }, "severity": { "type": "string", "enum": ["Critical","High","Medium"] }, "verdict": { "type": "string", "enum": ["BLOCK","WARN"] }, "fix": { "type": "string" } } } },
    "unit_tests": { "type": "array", "items": { "type": "object", "required": ["id","module","test","expected","regression_tag"], "additionalProperties": false, "properties": { "id": { "type": "string", "pattern": "^UT-\\d{2}$" }, "module": { "type": "string" }, "test": { "type": "string" }, "expected": { "type": "string" }, "regression_tag": { "type": "string", "enum": ["Smoke","Regression"] } } } },
    "integration_tests": { "type": "array", "items": { "type": "object", "required": ["id","scenario","precondition","steps","expected","http_status","regression_tag"], "additionalProperties": false, "properties": { "id": { "type": "string", "pattern": "^IT-\\d{2}$" }, "scenario": { "type": "string" }, "precondition": { "type": "string" }, "steps": { "type": "array", "items": { "type": "string" } }, "expected": { "type": "string" }, "http_status": { "type": "string" }, "regression_tag": { "type": "string", "enum": ["Smoke","Regression"] } } } },
    "e2e_tests": { "type": "array", "items": { "type": "object", "required": ["id","uc_ref","title","precondition","steps","expected_result","test_data","priority","regression_tag"], "additionalProperties": false, "properties": { "id": { "type": "string", "pattern": "^E2E-\\d{2}$" }, "uc_ref": { "type": "string" }, "title": { "type": "string" }, "precondition": { "type": "string" }, "steps": { "type": "array", "items": { "type": "string" } }, "expected_result": { "type": "string" }, "test_data": { "type": "string" }, "priority": { "type": "string", "enum": ["P1","P2","P3"] }, "regression_tag": { "type": "string", "enum": ["Smoke","Regression","Full"] } } } },
    "security_tests": { "type": "array", "items": { "type": "object", "required": ["id","owasp_category","scenario","steps","expected","severity"], "additionalProperties": false, "properties": { "id": { "type": "string", "pattern": "^SEC-\\d{2}$" }, "owasp_category": { "type": "string" }, "scenario": { "type": "string" }, "steps": { "type": "array", "items": { "type": "string" } }, "expected": { "type": "string" }, "severity": { "type": "string", "enum": ["Critical","High","Medium"] } } } },
    "performance_tests": { "type": "array", "items": { "type": "object", "required": ["id","scenario","tool","config","success_criteria"], "additionalProperties": false, "properties": { "id": { "type": "string", "pattern": "^PERF-\\d{2}$" }, "scenario": { "type": "string" }, "tool": { "type": "string" }, "config": { "type": "string" }, "success_criteria": { "type": "string" } } } },
    "a11y_tests": { "type": "array", "items": { "type": "object", "required": ["id","wcag_criterion","test","tool","expected"], "additionalProperties": false, "properties": { "id": { "type": "string", "pattern": "^A11Y-\\d{2}$" }, "wcag_criterion": { "type": "string" }, "test": { "type": "string" }, "tool": { "type": "string" }, "expected": { "type": "string" } } } },
    "test_data_sets": { "type": "array", "items": { "type": "object", "required": ["id","name","used_for","created_by","scope","reset_strategy"], "additionalProperties": false, "properties": { "id": { "type": "string", "pattern": "^TDATA-\\d{2}$" }, "name": { "type": "string" }, "used_for": { "type": "string" }, "created_by": { "type": "string" }, "scope": { "type": "string" }, "reset_strategy": { "type": "string" } } } },
    "uat_plan": {
      "type": "object", "required": ["participants","uat_tests","exit_criteria","defect_severity_matrix"], "additionalProperties": false,
      "properties": {
        "participants": { "type": "array", "items": { "type": "object", "required": ["stakeholder","role","feature_area","dates"], "additionalProperties": false, "properties": { "stakeholder": { "type": "string" }, "role": { "type": "string" }, "feature_area": { "type": "string" }, "dates": { "type": "string" } } } },
        "uat_tests": { "type": "array", "items": { "type": "object", "required": ["id","feature","business_scenario","actor","steps","expected_outcome"], "additionalProperties": false, "properties": { "id": { "type": "string", "pattern": "^UAT-\\d{2}$" }, "feature": { "type": "string" }, "business_scenario": { "type": "string" }, "actor": { "type": "string" }, "steps": { "type": "array", "items": { "type": "string" } }, "expected_outcome": { "type": "string" } } } },
        "exit_criteria": { "type": "array", "items": { "type": "object", "required": ["criteria","threshold","current"], "additionalProperties": false, "properties": { "criteria": { "type": "string" }, "threshold": { "type": "string" }, "current": { "type": ["string","null"] } } } },
        "defect_severity_matrix": { "type": "array", "items": { "type": "object", "required": ["severity","definition","example","sla_fix"], "additionalProperties": false, "properties": { "severity": { "type": "string", "enum": ["P1","P2","P3","P4"] }, "definition": { "type": "string" }, "example": { "type": "string" }, "sla_fix": { "type": "string" } } } }
      }
    },
    "regression_strategy": { "type": "array", "items": { "type": "object", "required": ["set","trigger","tc_included","estimated_run_min"], "additionalProperties": false, "properties": { "set": { "type": "string", "enum": ["Smoke","Regression","Full"] }, "trigger": { "type": "string" }, "tc_included": { "type": "string" }, "estimated_run_min": { "type": "integer" } } } }
  }
}
```

---

### Layer 4 — Human Template

```markdown
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

## Security Tests (OWASP Top 10)
| ID | OWASP | Scenario | Severity |
|----|-------|---------|---------|
{{#each security_tests}}
| {{id}} | {{owasp_category}} | {{scenario}} | {{severity}} |
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
```

---
---

## GPT-8 — Deployment Spec

### Layer 1 — Prompt

```
You are GPT-8 Deployment & Operations Spec in the MyGPT BA Suite pipeline.

Your job: produce deployment spec, CI/CD pipeline, monitoring & alerting rules, incident runbook, DR plan, and go-live checklist.
Output must be sufficient for a DevOps/SRE engineer without asking additional questions.

"Monitor the application" is NOT acceptable. Write "Alert when P95 response time > 500ms for 5 consecutive minutes."

OUTPUT RULES (NON-NEGOTIABLE):
- Respond ONLY with a single JSON object conforming to the Machine Template.
- IDs: ENV-01, STEP-01, ALERT-01, RUNBOOK-01, DR-01.
- Language: match the user's input language.

MACHINE TEMPLATE TO FILL:
{
  "ops_id": "<ISO date>-<slug>",
  "qa_ref": "<qa_id from GPT-7>",
  "environments": [
    { "id": "ENV-01", "name": "<dev|staging|prod>", "purpose": "", "infrastructure": "", "database": "", "external_services": "", "data": "", "access": "", "deploy_trigger": "", "backup": "" }
  ],
  "cicd_pipeline": {
    "branch_strategy": { "main": "", "develop": "", "feature": "", "hotfix": "" },
    "stages": [
      { "id": "STEP-01", "name": "", "tool": "", "duration_min": 0, "fail_condition": "" }
    ],
    "rollback_strategy": { "automatic": "", "manual_command": "", "db_rollback": "" }
  },
  "monitoring_alerts": [
    { "id": "ALERT-01", "metric": "", "condition": "", "severity": "<P1|P2|P3>", "channel": "", "action": "" }
  ],
  "dashboard_panels": [],
  "runbooks": [
    { "id": "RUNBOOK-01", "trigger": "", "severity": "<SEV-1|SEV-2|SEV-3|SEV-4>", "steps": [], "communicate_to": "", "post_incident_review": true }
  ],
  "dr_plan": [
    { "scenario": "", "rto": "", "rpo": "", "recovery_steps": [] }
  ],
  "go_live_checklist": {
    "technical": [],
    "process": [],
    "post_launch_48h": []
  }
}
```

---

### Layer 2 — Machine Template

```json
{
  "ops_id": "",
  "qa_ref": "",
  "environments": [
    { "id": "ENV-01", "name": "", "purpose": "", "infrastructure": "", "database": "", "external_services": "", "data": "", "access": "", "deploy_trigger": "", "backup": "" }
  ],
  "cicd_pipeline": {
    "branch_strategy": { "main": "", "develop": "", "feature": "", "hotfix": "" },
    "stages": [
      { "id": "STEP-01", "name": "", "tool": "", "duration_min": 0, "fail_condition": "" }
    ],
    "rollback_strategy": { "automatic": "", "manual_command": "", "db_rollback": "" }
  },
  "monitoring_alerts": [
    { "id": "ALERT-01", "metric": "", "condition": "", "severity": "", "channel": "", "action": "" }
  ],
  "dashboard_panels": [],
  "runbooks": [
    { "id": "RUNBOOK-01", "trigger": "", "severity": "", "steps": [], "communicate_to": "", "post_incident_review": true }
  ],
  "dr_plan": [
    { "scenario": "", "rto": "", "rpo": "", "recovery_steps": [] }
  ],
  "go_live_checklist": {
    "technical": [],
    "process": [],
    "post_launch_48h": []
  }
}
```

---

### Layer 3 — JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "gpt8-ops-output.schema.json",
  "title": "GPT-8 Deployment Spec Output",
  "type": "object",
  "required": ["ops_id","qa_ref","environments","cicd_pipeline","monitoring_alerts","dashboard_panels","runbooks","dr_plan","go_live_checklist"],
  "additionalProperties": false,
  "properties": {
    "ops_id": { "type": "string" }, "qa_ref": { "type": "string" },
    "environments": { "type": "array", "minItems": 3, "items": { "type": "object", "required": ["id","name","purpose","infrastructure","database","external_services","data","access","deploy_trigger","backup"], "additionalProperties": false, "properties": { "id": { "type": "string", "pattern": "^ENV-\\d{2}$" }, "name": { "type": "string", "enum": ["dev","staging","prod"] }, "purpose": { "type": "string" }, "infrastructure": { "type": "string" }, "database": { "type": "string" }, "external_services": { "type": "string" }, "data": { "type": "string" }, "access": { "type": "string" }, "deploy_trigger": { "type": "string" }, "backup": { "type": "string" } } } },
    "cicd_pipeline": {
      "type": "object", "required": ["branch_strategy","stages","rollback_strategy"], "additionalProperties": false,
      "properties": {
        "branch_strategy": { "type": "object", "required": ["main","develop","feature","hotfix"], "additionalProperties": false, "properties": { "main": { "type": "string" }, "develop": { "type": "string" }, "feature": { "type": "string" }, "hotfix": { "type": "string" } } },
        "stages": { "type": "array", "minItems": 5, "items": { "type": "object", "required": ["id","name","tool","duration_min","fail_condition"], "additionalProperties": false, "properties": { "id": { "type": "string", "pattern": "^STEP-\\d{2}$" }, "name": { "type": "string" }, "tool": { "type": "string" }, "duration_min": { "type": "integer" }, "fail_condition": { "type": "string" } } } },
        "rollback_strategy": { "type": "object", "required": ["automatic","manual_command","db_rollback"], "additionalProperties": false, "properties": { "automatic": { "type": "string" }, "manual_command": { "type": "string" }, "db_rollback": { "type": "string" } } }
      }
    },
    "monitoring_alerts": { "type": "array", "minItems": 4, "items": { "type": "object", "required": ["id","metric","condition","severity","channel","action"], "additionalProperties": false, "properties": { "id": { "type": "string", "pattern": "^ALERT-\\d{2}$" }, "metric": { "type": "string" }, "condition": { "type": "string" }, "severity": { "type": "string", "enum": ["P1","P2","P3"] }, "channel": { "type": "string" }, "action": { "type": "string" } } } },
    "dashboard_panels": { "type": "array", "items": { "type": "string" } },
    "runbooks": { "type": "array", "minItems": 1, "items": { "type": "object", "required": ["id","trigger","severity","steps","communicate_to","post_incident_review"], "additionalProperties": false, "properties": { "id": { "type": "string", "pattern": "^RUNBOOK-\\d{2}$" }, "trigger": { "type": "string" }, "severity": { "type": "string", "enum": ["SEV-1","SEV-2","SEV-3","SEV-4"] }, "steps": { "type": "array", "items": { "type": "string" } }, "communicate_to": { "type": "string" }, "post_incident_review": { "type": "boolean" } } } },
    "dr_plan": { "type": "array", "minItems": 3, "items": { "type": "object", "required": ["scenario","rto","rpo","recovery_steps"], "additionalProperties": false, "properties": { "scenario": { "type": "string" }, "rto": { "type": "string" }, "rpo": { "type": "string" }, "recovery_steps": { "type": "array", "items": { "type": "string" } } } } },
    "go_live_checklist": { "type": "object", "required": ["technical","process","post_launch_48h"], "additionalProperties": false, "properties": { "technical": { "type": "array", "items": { "type": "string" } }, "process": { "type": "array", "items": { "type": "string" } }, "post_launch_48h": { "type": "array", "items": { "type": "string" } } } }
  }
}
```

---

### Layer 4 — Human Template

```markdown
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
```

---
---

## GPT-9 — Change & Release Manager

### Layer 1 — Prompt

```
You are GPT-9 Change & Release Manager in the MyGPT BA Suite pipeline.

You handle two workflows:
WORKFLOW A — Change Request Analysis: analyze impact across 6 dimensions (Module/API/Database/UI/Business Rules/Tests), classify risk, estimate effort, recommend rollback plan.
WORKFLOW B — Release Artifacts: generate Release Note, update Function List, generate UAT Report, update Risk Log.

"System affected" is NOT acceptable. Write "Module: OrderService — API: POST /orders — add field 'priority' — breaking: No".

OUTPUT RULES (NON-NEGOTIABLE):
- Respond ONLY with a single JSON object conforming to the Machine Template.
- IDs: CR-XX, FL-XX, RISK-XXX, DEF-XXX.
- Language: match the user's input language.

MACHINE TEMPLATE TO FILL:
{
  "release_id": "<ISO date>-v<X.Y.Z>",
  "ops_ref": "<ops_id from GPT-8>",
  "workflow": "<A_change_request|B_release_artifacts>",
  "change_request": {
    "id": "CR-01",
    "title": "",
    "requested_by": "",
    "priority": "<Critical|High|Medium|Low>",
    "type": "<New Feature|Enhancement|Bug Fix|Regulatory>",
    "status": "<Draft|In Review|Approved|In Progress|Done>",
    "description": "",
    "business_justification": "",
    "current_behavior": "",
    "expected_behavior": "",
    "impact_analysis": {
      "modules": [{ "module": "", "impact": "<High|Medium|Low>", "change_type": "", "effort": "<S|M|L|XL>", "notes": "" }],
      "apis": [{ "endpoint": "", "method": "", "impact": "", "change_type": "", "breaking_change": false, "version_bump": false }],
      "database": [{ "table": "", "column": "", "change_type": "", "migration_required": false, "data_migration": false, "rollback_script": false }],
      "ui_screens": [{ "screen": "", "component": "", "impact": "", "change_required": "" }],
      "business_rules": [{ "br_id": "", "current_rule": "", "new_rule": "", "conflict": false, "action": "" }],
      "test_impact": [{ "suite": "", "tests_affected": "", "rewrite_required": false, "regression_risk": "<High|Medium|Low>" }]
    },
    "risk_level": "<Critical|High|Medium|Low>",
    "rollback_plan": [],
    "effort_estimate": { "development": "", "testing": "", "total": "" }
  },
  "function_list": [
    { "id": "", "category": "", "great_function": "", "medium_function": "", "small_function": "", "description": "", "priority": "", "status": "<Confirmed|In Progress|Reviewing (UAT)|Ready for Release|Released|Backlog>", "added_date": "" }
  ],
  "release_note": {
    "system_name": "",
    "version": "",
    "release_date": "",
    "release_manager": "",
    "objectives": [],
    "changes": [{ "ref_id": "", "description": "", "type": "<New Feature|Enhancement|Bug Fix>", "notes": "" }],
    "breaking_changes": [],
    "known_issues": [],
    "rollback_plan": []
  },
  "risk_log": [
    { "id": "RISK-001", "category": "<Technical|Business|Data|Resource|External|Security|Compliance>", "description": "", "impact": "<High|Medium|Low>", "probability": "<High|Medium|Low>", "resolution_plan": "", "owner": "", "due_date": "", "status": "<Open|In Progress|Mitigated|Closed>" }
  ]
}
```

---

### Layer 2 — Machine Template

```json
{
  "release_id": "",
  "ops_ref": "",
  "workflow": "",
  "change_request": {
    "id": "CR-01", "title": "", "requested_by": "", "priority": "", "type": "", "status": "",
    "description": "", "business_justification": "", "current_behavior": "", "expected_behavior": "",
    "impact_analysis": {
      "modules": [{ "module": "", "impact": "", "change_type": "", "effort": "", "notes": "" }],
      "apis": [{ "endpoint": "", "method": "", "impact": "", "change_type": "", "breaking_change": false, "version_bump": false }],
      "database": [{ "table": "", "column": "", "change_type": "", "migration_required": false, "data_migration": false, "rollback_script": false }],
      "ui_screens": [{ "screen": "", "component": "", "impact": "", "change_required": "" }],
      "business_rules": [{ "br_id": "", "current_rule": "", "new_rule": "", "conflict": false, "action": "" }],
      "test_impact": [{ "suite": "", "tests_affected": "", "rewrite_required": false, "regression_risk": "" }]
    },
    "risk_level": "",
    "rollback_plan": [],
    "effort_estimate": { "development": "", "testing": "", "total": "" }
  },
  "function_list": [
    { "id": "", "category": "", "great_function": "", "medium_function": "", "small_function": "", "description": "", "priority": "", "status": "", "added_date": "" }
  ],
  "release_note": {
    "system_name": "", "version": "", "release_date": "", "release_manager": "",
    "objectives": [],
    "changes": [{ "ref_id": "", "description": "", "type": "", "notes": "" }],
    "breaking_changes": [], "known_issues": [], "rollback_plan": []
  },
  "risk_log": [
    { "id": "RISK-001", "category": "", "description": "", "impact": "", "probability": "", "resolution_plan": "", "owner": "", "due_date": "", "status": "" }
  ]
}
```

---

### Layer 3 — JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "gpt9-release-output.schema.json",
  "title": "GPT-9 Change & Release Manager Output",
  "type": "object",
  "required": ["release_id","ops_ref","workflow","change_request","function_list","release_note","risk_log"],
  "additionalProperties": false,
  "properties": {
    "release_id": { "type": "string" },
    "ops_ref": { "type": "string" },
    "workflow": { "type": "string", "enum": ["A_change_request","B_release_artifacts"] },
    "change_request": {
      "type": "object",
      "required": ["id","title","requested_by","priority","type","status","description","business_justification","current_behavior","expected_behavior","impact_analysis","risk_level","rollback_plan","effort_estimate"],
      "additionalProperties": false,
      "properties": {
        "id": { "type": "string", "pattern": "^CR-\\d{2}$" },
        "title": { "type": "string" }, "requested_by": { "type": "string" },
        "priority": { "type": "string", "enum": ["Critical","High","Medium","Low"] },
        "type": { "type": "string", "enum": ["New Feature","Enhancement","Bug Fix","Regulatory"] },
        "status": { "type": "string", "enum": ["Draft","In Review","Approved","In Progress","Done"] },
        "description": { "type": "string" }, "business_justification": { "type": "string" },
        "current_behavior": { "type": "string" }, "expected_behavior": { "type": "string" },
        "impact_analysis": { "type": "object", "required": ["modules","apis","database","ui_screens","business_rules","test_impact"], "additionalProperties": false,
          "properties": {
            "modules": { "type": "array", "items": { "type": "object", "required": ["module","impact","change_type","effort","notes"], "additionalProperties": false, "properties": { "module": { "type": "string" }, "impact": { "type": "string", "enum": ["High","Medium","Low"] }, "change_type": { "type": "string" }, "effort": { "type": "string", "enum": ["S","M","L","XL"] }, "notes": { "type": "string" } } } },
            "apis": { "type": "array", "items": { "type": "object", "required": ["endpoint","method","impact","change_type","breaking_change","version_bump"], "additionalProperties": false, "properties": { "endpoint": { "type": "string" }, "method": { "type": "string" }, "impact": { "type": "string" }, "change_type": { "type": "string" }, "breaking_change": { "type": "boolean" }, "version_bump": { "type": "boolean" } } } },
            "database": { "type": "array", "items": { "type": "object", "required": ["table","column","change_type","migration_required","data_migration","rollback_script"], "additionalProperties": false, "properties": { "table": { "type": "string" }, "column": { "type": "string" }, "change_type": { "type": "string" }, "migration_required": { "type": "boolean" }, "data_migration": { "type": "boolean" }, "rollback_script": { "type": "boolean" } } } },
            "ui_screens": { "type": "array", "items": { "type": "object", "required": ["screen","component","impact","change_required"], "additionalProperties": false, "properties": { "screen": { "type": "string" }, "component": { "type": "string" }, "impact": { "type": "string" }, "change_required": { "type": "string" } } } },
            "business_rules": { "type": "array", "items": { "type": "object", "required": ["br_id","current_rule","new_rule","conflict","action"], "additionalProperties": false, "properties": { "br_id": { "type": "string" }, "current_rule": { "type": "string" }, "new_rule": { "type": "string" }, "conflict": { "type": "boolean" }, "action": { "type": "string" } } } },
            "test_impact": { "type": "array", "items": { "type": "object", "required": ["suite","tests_affected","rewrite_required","regression_risk"], "additionalProperties": false, "properties": { "suite": { "type": "string" }, "tests_affected": { "type": "string" }, "rewrite_required": { "type": "boolean" }, "regression_risk": { "type": "string", "enum": ["High","Medium","Low"] } } } }
          }
        },
        "risk_level": { "type": "string", "enum": ["Critical","High","Medium","Low"] },
        "rollback_plan": { "type": "array", "items": { "type": "string" } },
        "effort_estimate": { "type": "object", "required": ["development","testing","total"], "additionalProperties": false, "properties": { "development": { "type": "string" }, "testing": { "type": "string" }, "total": { "type": "string" } } }
      }
    },
    "function_list": { "type": "array", "items": { "type": "object", "required": ["id","category","great_function","medium_function","small_function","description","priority","status","added_date"], "additionalProperties": false, "properties": { "id": { "type": "string" }, "category": { "type": "string" }, "great_function": { "type": "string" }, "medium_function": { "type": "string" }, "small_function": { "type": "string" }, "description": { "type": "string" }, "priority": { "type": "string" }, "status": { "type": "string", "enum": ["Confirmed","In Progress","Reviewing (UAT)","Ready for Release","Released","Backlog"] }, "added_date": { "type": "string" } } } },
    "release_note": { "type": "object", "required": ["system_name","version","release_date","release_manager","objectives","changes","breaking_changes","known_issues","rollback_plan"], "additionalProperties": false, "properties": { "system_name": { "type": "string" }, "version": { "type": "string" }, "release_date": { "type": "string" }, "release_manager": { "type": "string" }, "objectives": { "type": "array", "items": { "type": "string" } }, "changes": { "type": "array", "items": { "type": "object", "required": ["ref_id","description","type","notes"], "additionalProperties": false, "properties": { "ref_id": { "type": "string" }, "description": { "type": "string" }, "type": { "type": "string", "enum": ["New Feature","Enhancement","Bug Fix"] }, "notes": { "type": "string" } } } }, "breaking_changes": { "type": "array", "items": { "type": "string" } }, "known_issues": { "type": "array", "items": { "type": "string" } }, "rollback_plan": { "type": "array", "items": { "type": "string" } } } },
    "risk_log": { "type": "array", "items": { "type": "object", "required": ["id","category","description","impact","probability","resolution_plan","owner","due_date","status"], "additionalProperties": false, "properties": { "id": { "type": "string", "pattern": "^RISK-\\d{3}$" }, "category": { "type": "string", "enum": ["Technical","Business","Data","Resource","External","Security","Compliance"] }, "description": { "type": "string" }, "impact": { "type": "string", "enum": ["High","Medium","Low"] }, "probability": { "type": "string", "enum": ["High","Medium","Low"] }, "resolution_plan": { "type": "string" }, "owner": { "type": "string" }, "due_date": { "type": "string" }, "status": { "type": "string", "enum": ["Open","In Progress","Mitigated","Closed"] } } } }
  }
}
```

---

### Layer 4 — Human Template

```markdown
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

{{#if release_note.breaking_changes}}
## ⚠️ Breaking Changes
{{#each release_note.breaking_changes}}
- {{this}}
{{/each}}
{{/if}}

## Change Request — {{change_request.id}}
**Risk level:** {{change_request.risk_level}} | **Status:** {{change_request.status}}

### Impact Analysis
**Modules:** {{change_request.impact_analysis.modules | map 'module' | join ", "}}
**APIs với breaking change:** {{change_request.impact_analysis.apis | filter 'breaking_change' | map 'endpoint' | join ", "}}
**DB tables cần migration:** {{change_request.impact_analysis.database | filter 'migration_required' | map 'table' | join ", "}}

### Effort Estimate
Dev: {{change_request.effort_estimate.development}} | QA: {{change_request.effort_estimate.testing}} | Total: {{change_request.effort_estimate.total}}

### Rollback Plan
{{#each change_request.rollback_plan}}
{{@index_plus_1}}. {{this}}
{{/each}}

## Function List

| ID | Category | Chức năng lớn | Chức năng nhỏ | Status |
|----|---------|--------------|--------------|--------|
{{#each function_list}}
| {{id}} | {{category}} | {{great_function}} | {{small_function}} | {{status}} |
{{/each}}

## Risk Log

| ID | Category | Mô tả | Impact | P | Status | Owner | Due |
|----|---------|-------|--------|---|--------|-------|-----|
{{#each risk_log}}
| {{id}} | {{category}} | {{description}} | {{impact}} | {{probability}} | {{status}} | {{owner}} | {{due_date}} |
{{/each}}
```

---

## Mapping Guarantee Summary (toàn pipeline)

| Agent | Prompt enforces | Schema blocks drift via | Human Template renders |
|-------|----------------|------------------------|----------------------|
| GPT-1 | Skeleton JSON embedded | `required` + `additionalProperties: false` + `pattern` | Intake Report |
| GPT-2 | 6 dimension labels + verdict enum | `enum: [ok, incomplete, logic_error]` + ID patterns | Review Report |
| GPT-3 | Monolith rule + team context gate | `enum: [monolith, modular_monolith, microservices]` | Solution Design |
| GPT-4 | "must/shall" language + Glossary first | `pattern: ^UC-\d{2}$` + VR trigger enum | SRS/BRD/UC doc |
| GPT-5 | INVEST + Gherkin mandatory | `minItems: 2` on AC + INVEST boolean object | User Stories |
| GPT-6 | State enum enforced | `enum: [Loading, Success, Empty, Error, ...]` | FE Tech Spec |
| GPT-7 | Level-ownership separation + OWASP ref | `enum: [BLOCK, WARN]` + test level ID patterns | QA Plan + UAT |
| GPT-8 | Specific alert conditions, no vague strings | `minItems` on environments/stages/alerts | Ops Runbook |
| GPT-9 | 6-dimension impact + breaking_change boolean | `enum` on workflow/risk/status + RISK pattern | Release Note |
