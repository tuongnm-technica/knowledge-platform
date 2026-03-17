from __future__ import annotations

from typing import Any


SUPPORTED_DOC_TYPES: dict[str, str] = {
    "srs": "SRS (Software Requirements Specification)",
    "brd": "BRD (Business Requirements Document)",
    "use_cases": "Use Cases",
    "validation_rules": "Validation Rules",
    "user_stories": "User Stories + Acceptance Criteria",
    "api_spec": "API Specification",
    "requirements_intake": "Requirements Intake (FR/NFR/BR + Assumptions)",
    "requirement_review": "Requirement Review (Gaps/Risks/Permissions)",
    "solution_design": "Solution Design (Architecture + ADR + Data Model)",
    "fe_spec": "FE Technical Spec (Components + UI States + a11y)",
    "qa_test_spec": "QA Test Spec (Unit/IT/E2E/UAT + OWASP)",
    "deployment_spec": "Deployment & Ops Spec (CI/CD + Monitoring + Runbook)",
    "change_request": "Change Request Analysis + Impact Analysis",
    "release_notes": "Release Notes",
    "function_list": "Function List",
    "risk_log": "Risk Log",
}

PROMPT_EXTENSIONS: dict[str, str] = {
    "api_spec": "Tạo API Specification: endpoints, params, request/response JSON examples, error model (RFC 7807), status codes.\n",
    "requirements_intake": "Tạo Requirements Intake: danh sách BR/FR/NFR atomic & testable + assumptions/constraints + open questions.\n",
    "requirement_review": "Review requirement: tìm gaps, conflicts BR/FR/UC/VR, edge cases, permission model, risks; nêu verdict (BLOCK/WARN/OK).\n",
    "solution_design": "Tạo Solution Design: architecture overview, ADRs (decision + rationale), data model high-level, integration points, non-functional considerations.\n",
    "fe_spec": "Tạo FE Technical Spec: component tree, component contracts, UI state matrix, validation UX behavior, error boundary, a11y (WCAG 2.1 AA), performance budget.\n",
    "qa_test_spec": "Tạo QA Test Spec: consistency checks (BLOCK/WARN), test cases theo level (Unit/Integration/E2E/UAT) + owner + test data; security tests map OWASP Top 10 (2021); UAT exit criteria.\n",
    "deployment_spec": "Tạo Deployment & Ops Spec: environments, CI/CD, config/secrets, monitoring & alerting thresholds, incident runbook, DR plan, go-live checklist.\n",
    "change_request": "Tạo Change Request analysis + impact analysis 6 dimensions (Module/API/DB/UI/BR/Tests), risk classification, effort estimate, rollback plan.\n",
    "release_notes": "Tạo Release Notes: What's new, improvements, bug fixes, known issues, rollback notes, version/date.\n",
    "function_list": "Tạo Function List: danh sách chức năng module/feature/function + owner + status + link tới FR/UC.\n",
    "risk_log": "Tạo Risk Log: risk id, description, likelihood/impact, mitigation, owner, due date, status.\n",
    "brd": "Tạo BRD: problem statement, stakeholders, scope, assumptions, success metrics, risks.\n",
    "use_cases": "Tạo Use Case chi tiết: main flow + exception flows + pre/post conditions.\n",
    "validation_rules": "Tạo Validation Rules có UX behavior: khi nào validate, message, FE/BE rule.\n",
    "user_stories": "Tạo User Stories theo INVEST + Gherkin AC + DoD.\n",
    "srs": "Tạo SRS theo cấu trúc 10 mục (có Glossary + Traceability).\n",
}

OUTPUT_STRUCTURES: dict[str, str] = {
    "srs": (
        "Tạo SRS theo mục lục:\n"
        "0) Glossary\n"
        "1) Giới thiệu (Scope/Out of scope/Stakeholders/Assumptions)\n"
        "2) Tổng quan giải pháp\n"
        "3) Business Rules (BR-xx)\n"
        "4) Functional Requirements (FR-xx)\n"
        "5) Non-Functional Requirements (NFR-xx)\n"
        "6) Data Model (high-level)\n"
        "7) API Specification (high-level)\n"
        "8) UI/UX Notes (nếu có)\n"
        "9) Traceability Matrix (FR ↔ UC ↔ VR) + Open Questions\n"
    ),
    "api_spec": (
        "API Spec structure:\n"
        "- Overview + assumptions\n"
        "- Authentication/Authorization\n"
        "- Error model (RFC 7807) + common error codes\n"
        "- Endpoints table\n"
        "- Per-endpoint details: request/response JSON examples, validations, status codes, idempotency, pagination (nếu có)\n"
    ),
    "requirements_intake": (
        "Xuất danh sách atomic:\n"
        "- Business Rules (BR-xx)\n"
        "- Functional Requirements (FR-xx)\n"
        "- Non-Functional Requirements (NFR-xx)\n"
        "- Assumptions/Constraints\n"
        "- Open questions (TBD) + ai có thể trả lời\n"
    ),
    "requirement_review": (
        "- Verdict: BLOCK/WARN/OK\n"
        "- Issues table: conflict/gap/edge case/permission risk + fix recommendation\n"
        "- Missing info / questions\n"
    ),
    "solution_design": (
        "- Context + goals\n"
        "- Architecture overview (modules + integrations)\n"
        "- ADR list (Decision, Options, Rationale)\n"
        "- Data model high-level (entities + relations)\n"
        "- API contract overview (endpoints summary)\n"
        "- NFR considerations + tradeoffs\n"
    ),
    "fe_spec": (
        "- Component architecture + contracts\n"
        "- UI state matrix (loading/success/empty/error/partial)\n"
        "- Validation UX spec\n"
        "- API integration spec (status-code handling)\n"
        "- a11y requirements + focus management\n"
        "- Error boundary + monitoring hooks\n"
        "- Performance budget\n"
    ),
    "qa_test_spec": (
        "- Consistency check table (CHK-xx) + verdict\n"
        "- Test cases chia theo level (UT/IT/E2E/UAT) + owner + test data\n"
        "- Security tests map OWASP 2021\n"
        "- UAT plan + exit criteria + defect severity matrix\n"
    ),
    "deployment_spec": (
        "- Environment specs (dev/staging/prod)\n"
        "- CI/CD pipeline flow + gates + rollback\n"
        "- Config/secrets management\n"
        "- Monitoring & alerting thresholds\n"
        "- Incident runbook + DR plan\n"
        "- Go-live checklist\n"
    ),
    "change_request": (
        "- CR template (current vs expected)\n"
        "- Impact analysis 6 dimensions + breaking change flag\n"
        "- Risk classification + recommended actions + rollback plan\n"
    ),
    "release_notes": (
        "- Version/date\n"
        "- What's new / Improvements / Bug fixes\n"
        "- Known issues\n"
        "- Rollback notes\n"
    ),
    "function_list": "- Bảng Function List: Module/Feature/Function, Description, Owner, Status, Related IDs (FR/UC/US)\n",
    "risk_log": "- Bảng Risk Log: Risk-ID, Description, Likelihood, Impact, Mitigation, Owner, Due date, Status\n",
    "brd": "BRD sections: Background, Problem, Goals, Scope, Stakeholders, Assumptions/Constraints, Risks, Success metrics.\n",
    "use_cases": "Mỗi UC gồm: UC-ID, Actors, Preconditions, Trigger, Main flow, Alternate/Exception flows, Postconditions.\n",
    "validation_rules": "Danh sách VR-xx: rule, trigger timing, UX behavior, FE rule, BE rule, error message.\n",
    "user_stories": "US-xx theo format 'As a ... I want ... so that ...' + Gherkin AC + DoD.\n",
}


def build_doc_system_prompt(*, doc_type: str) -> str:
    doc_type = (doc_type or "srs").strip().lower()
    base = (
        "You are a senior Business Analyst producing enterprise-grade documentation in Vietnamese.\n"
        "Golden rules:\n"
        "- Không bịa business rule. Thiếu thông tin thì ghi 'TBD' và liệt kê câu hỏi cần làm rõ.\n"
        "- Viết rõ ràng, kiểm thử được: dùng 'must/shall', tránh 'có thể/should'.\n"
        "- ID nhất quán: BR-01, FR-01, NFR-01, UC-01, VR-01, US-01 (tăng dần).\n"
        "- Output là Markdown.\n"
    )

    extension = PROMPT_EXTENSIONS.get(doc_type, PROMPT_EXTENSIONS["srs"])
    return base + extension


def build_doc_user_prompt(
    *,
    doc_type: str,
    question: str,
    answer: str,
    sources: list[dict[str, Any]],
    documents: list[dict[str, Any]],
) -> str:
    doc_type = (doc_type or "srs").strip().lower()
    label = SUPPORTED_DOC_TYPES.get(doc_type, doc_type)

    lines: list[str] = []
    lines.append(f"Hãy tạo tài liệu dạng **{label}** dựa trên thông tin sau.")
    lines.append("")
    if question:
        lines.append("## User request")
        lines.append(str(question).strip())
        lines.append("")
    if answer:
        lines.append("## Current AI answer (high-level)")
        lines.append(str(answer).strip())
        lines.append("")

    lines.append("## Selected sources (top)")
    for idx, s in enumerate((sources or [])[:12], start=1):
        title = str(s.get("title") or "").strip() or "Untitled"
        url = str(s.get("url") or "").strip()
        src = str(s.get("source") or "").strip()
        doc_id = str(s.get("document_id") or "").strip()
        lines.append(f"{idx}. [{src}] {title}")
        if url:
            lines.append(f"   - url: {url}")
        if doc_id:
            lines.append(f"   - document_id: {doc_id}")
        snippet = str(s.get("snippet") or s.get("quote") or "").strip()
        if snippet:
            lines.append(f"   - snippet: {snippet[:320]}")
    lines.append("")

    lines.append("## Document details (condensed)")
    lines.append("Dưới đây là nội dung chi tiết của các tài liệu (được bọc trong thẻ <document>):")
    for d in (documents or [])[:10]:
        title = str(d.get("title") or "").strip() or "Untitled"
        source = str(d.get("source") or "").strip()
        url = str(d.get("url") or "").strip()
        updated = str(d.get("updated_at") or "").strip()
        content = str(d.get("content") or "").strip()
        content = content[:1800]
        lines.append(f"### [{source}] {title}")
        if url:
            lines.append(f"- url: {url}")
        if updated:
            lines.append(f"- updated_at: {updated}")
        if content:
            lines.append("<document>")
            lines.append(content)
            lines.append("</document>\n")

    # Load the specific output structure from the dictionary
    structure_hint = OUTPUT_STRUCTURES.get(doc_type)
    if structure_hint:
        lines.append("## Output requirements\n")
        lines.append(structure_hint)

    return "\n".join(lines).strip() + "\n"
