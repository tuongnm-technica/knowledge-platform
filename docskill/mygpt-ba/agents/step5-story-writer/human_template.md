— Human Template

# User Stories (Sprint Backlog)
**Document Reference:** {{doc_ref}}
**Sprint Goal:** {{sprint_goal}}

{{#each epics}}
## 🎯 Epic: {{summary}}
**Description:** {{description}}
**Labels:** `{{labels | join ", "}}`

---
{{#each stories}}
### 📝 Story: {{summary}} ({{story_points}} SP)
**Labels:** `{{labels | join ", "}}`

**User Story:** 
> {{user_story_statement}}

**Context & Notes:**
{{context_notes}}

**Acceptance Criteria (Gherkin):**
{{#each acceptance_criteria}}
```gherkin
{{this}}

{{/each}}

**Technical Sub-tasks:**
{{#each subtasks}}
- [ ] [{{component}}] {{summary}}
{{/each}}

<br>
{{/each}}
{{/each}}