import os
from pathlib import Path
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

# ─────────────────────────────────────────────────────────────────────────────
# mygpt-ba Skill — 9-Agent BA Pipeline (docskill/mygpt-ba)
# Each key maps to the doc_type that maps to that agent's expertise.
# ─────────────────────────────────────────────────────────────────────────────
SKILL_AGENT_LABELS: dict[str, tuple[str, str, str]] = {
    # doc_type → (agent label, short description, group)
    "requirements_intake": (
        "📋 GPT-1: Requirement Analyst",
        "Biến idea thô → FR · NFR · BR · Assumptions · Traceability seed",
        "Phân tích yêu cầu",
    ),
    "requirement_review": (
        "🔍 GPT-2: Architect Reviewer",
        "Review business logic · Permission model · Edge cases · BR conflicts",
        "Kiến trúc & Review",
    ),
    "solution_design": (
        "🏗️ GPT-3: Solution Designer",
        "Architecture + ADR · API contract · Data model · Deployment topology",
        "Giải pháp kỹ thuật",
    ),
    "srs": (
        "📄 GPT-4: Document Writer — SRS",
        "SRS 10 mục + Glossary + Traceability Matrix",
        "Tài liệu đặc tả",
    ),
    "brd": (
        "📋 GPT-4: Document Writer — BRD",
        "BRD đầy đủ business case (12 or 17-section)",
        "Tài liệu đặc tả",
    ),
    "use_cases": (
        "📐 GPT-4: Document Writer — Use Cases",
        "Use Cases chi tiết + FE Technical Notes",
        "Tài liệu đặc tả",
    ),
    "validation_rules": (
        "✅ GPT-4: Document Writer — Validation Rules",
        "Validation Rules với UX behavior (FE + BE rules)",
        "Tài liệu đặc tả",
    ),
    "user_stories": (
        "🎯 GPT-5: User Story Writer",
        "User Stories · Gherkin AC · INVEST · DoD · Epic→Story→Task",
        "User Story & Task",
    ),
    "fe_spec": (
        "🖥️ GPT-6: FE Technical Spec",
        "Component tree · UI State matrix · a11y · Error boundary · Perf budget",
        "Phát triển FE",
    ),
    "qa_test_spec": (
        "🧪 GPT-7: QA Reviewer",
        "Test cases (5 levels) · OWASP · UAT exit criteria · Test data strategy",
        "Kiểm thử & QA",
    ),
    "api_spec": (
        "🔌 GPT-3: API Spec (Solution Designer)",
        "OpenAPI spec skeleton · RFC 7807 errors · Status codes · Idempotency",
        "Giải pháp kỹ thuật",
    ),
    "deployment_spec": (
        "🚀 GPT-8: Deployment Spec",
        "CI/CD · Environment config · Monitoring alerts · Runbook · DR plan",
        "Triển khai & Vận hành",
    ),
    "change_request": (
        "📝 GPT-9: Change & Release Mgr — CR",
        "Change Request · Impact Analysis 6 dimensions · Risk · Rollback plan",
        "Thay đổi & Phát hành",
    ),
    "release_notes": (
        "📢 GPT-9: Change & Release Mgr — Release Notes",
        "Release Notes: What's new · Improvements · Bug fixes · Rollback",
        "Thay đổi & Phát hành",
    ),
    "function_list": (
        "📊 GPT-9: Change & Release Mgr — Function List",
        "Function List: Module/Feature/Function + Status + Links",
        "Thay đổi & Phát hành",
    ),
    "risk_log": (
        "⚠️ GPT-9: Change & Release Mgr — Risk Log",
        "Risk Log: Risk-ID · Likelihood · Impact · Mitigation · Owner",
        "Thay đổi & Phát hành",
    ),
}

# Detailed system instructions extracted from mygpt-ba references
# ─────────────────────────────────────────────────────────────────────────────
# reference mapping for Hybrid Edition (20KB+ deep prompts)
# ─────────────────────────────────────────────────────────────────────────────
SKILL_REF_FILES: dict[str, str] = {
    "requirements_intake": "gpt1-requirement-analyst.md",
    "requirement_review": "gpt2-architect-reviewer.md",
    "solution_design": "gpt3-solution-designer.md",
    "api_spec": "gpt3-solution-designer.md",
    "srs": "gpt4-document-writer.md",
    "brd": "gpt4-document-writer.md",
    "use_cases": "gpt4-document-writer.md",
    "validation_rules": "gpt4-document-writer.md",
    "user_stories": "gpt5-user-story-writer.md",
    "fe_spec": "gpt6-fe-technical-spec.md",
    "qa_test_spec": "gpt7-qa-reviewer.md",
    "deployment_spec": "gpt8-deployment-spec.md",
    "change_request": "gpt9-change-release-mgr.md",
    "release_notes": "gpt9-change-release-mgr.md",
    "function_list": "gpt9-change-release-mgr.md",
    "risk_log": "gpt9-change-release-mgr.md",
}

def get_ref_path(filename: str) -> Path:
    # Works in both local and Docker (/app)
    base = Path(__file__).parent.parent
    return base / "docskill" / "mygpt-ba" / "references" / filename

def load_full_prompt(doc_type: str) -> str:
    fname = SKILL_REF_FILES.get(doc_type)
    if not fname:
        return ""
    path = get_ref_path(fname)
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""
    return ""

# Initialize with full prompts from filesystem
SKILL_SYSTEM_PROMPTS: dict[str, str] = {
    doc_type: load_full_prompt(doc_type)
    for doc_type in SKILL_REF_FILES
}

# Map doc_type → agent label for display in UI
SKILL_DOC_TYPE_GROUPS: dict[str, list[str]] = {
    "📋 GPT-1: Requirement Analyst": ["requirements_intake"],
    "🔍 GPT-2: Architect Reviewer": ["requirement_review"],
    "🏗️ GPT-3: Solution Designer": ["solution_design", "api_spec"],
    "📄 GPT-4: Document Writer": ["srs", "brd", "use_cases", "validation_rules"],
    "🎯 GPT-5: User Story Writer": ["user_stories"],
    "🖥️ GPT-6: FE Technical Spec": ["fe_spec"],
    "🧪 GPT-7: QA Reviewer": ["qa_test_spec"],
    "🚀 GPT-8: Deployment Spec": ["deployment_spec"],
    "📝 GPT-9: Change & Release Mgr": ["change_request", "release_notes", "function_list", "risk_log"],
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

# ─────────────────────────────────────────────────────────────────────────────
# Knowledge Injection Mapping
# Maps doc_type to related expert knowledge files in knowledge_base/standards/
# ─────────────────────────────────────────────────────────────────────────────
KNOWLEDGE_MAPPING: dict[str, list[str]] = {
    "requirements_intake": ["ba_standards.md", "language_standards.md"],
    "requirement_review": ["ba_standards.md", "sa_standards.md", "solution_design_standards.md", "language_standards.md"],
    "solution_design": ["sa_standards.md", "solution_design_standards.md", "be_dev_standards.md", "language_standards.md"],
    "api_spec": ["sa_standards.md", "solution_design_standards.md", "be_dev_standards.md", "language_standards.md"],
    "srs": ["ba_standards.md", "language_standards.md"],
    "brd": ["ba_standards.md", "language_standards.md"],
    "use_cases": ["ba_standards.md", "language_standards.md"],
    "validation_rules": ["ba_standards.md", "language_standards.md"],
    "user_stories": ["ba_standards.md", "language_standards.md"],
    "fe_spec": ["solution_design_standards.md", "fe_dev_standards.md", "language_standards.md"],
    "qa_test_spec": ["qa_standards.md", "language_standards.md"],
    "deployment_spec": ["solution_design_standards.md", "qa_standards.md", "be_dev_standards.md", "language_standards.md"],
    "change_request": ["ba_standards.md", "language_standards.md"],
    "release_notes": ["ba_standards.md", "language_standards.md"],
    "function_list": ["ba_standards.md", "language_standards.md"],
    "risk_log": ["ba_standards.md", "language_standards.md"],
}

def get_expert_knowledge(doc_type: str) -> str:
    files = KNOWLEDGE_MAPPING.get(doc_type, ["ba_standards.md"])
    base_path = Path(__file__).parent.parent / "knowledge_base" / "standards"
    
    knowledge_blocks = []
    for fname in files:
        p = base_path / fname
        if p.exists():
            try:
                content = p.read_text(encoding="utf-8")
                knowledge_blocks.append(f"### KIẾN THỨC CHUYÊN GIA: {fname}\n{content}")
            except Exception:
                continue
                
    if not knowledge_blocks:
        return ""
        
    return "\n\n## TRI THỨC NỀN TẢNG (EXPERT KNOWLEDGE)\nSử dụng các tiêu chuẩn và tri thức sau đây làm kim chỉ nam để thực hiện Skill này:\n\n" + "\n\n".join(knowledge_blocks)


def build_doc_system_prompt(*, doc_type: str, db_prompt: str | None = None) -> str:
    doc_type = (doc_type or "srs").strip().lower()

    # Highest priority: user-customized prompt stored in DB
    if db_prompt and db_prompt.strip():
        base = (
            "Yêu cầu quan trọng nhất: TOÀN BỘ nội dung tài liệu phải được viết bằng TIẾNG VIỆT chuyên nghiệp, giàu thông tin, không trình bày chung chung.\n"
            "ID nhất quán: BR-01, FR-01, NFR-01, UC-01, VR-01, US-01 (tăng dần xuyên suốt).\n"
            "Output phải là Markdown đầy đủ, phân tích sâu các khía cạnh nghiệp vụ và kỹ thuật.\n\n"
        )
        return db_prompt.strip() + "\n\n" + base

    # Second priority: hardcoded mygpt-ba skill prompt
    if doc_type in SKILL_SYSTEM_PROMPTS:
        base = (
            "Yêu cầu quan trọng nhất: TOÀN BỘ nội dung tài liệu phải được viết bằng TIẾNG VIỆT chuyên nghiệp, giàu thông tin, phân tích đa chiều, tránh viết ngắn gọn hời hợt.\n"
            "ID nhất quán: BR-01, FR-01, NFR-01, UC-01, VR-01, US-01 (tăng dần xuyên suốt).\n"
            "Output phải là Markdown đầy đủ, chi tiết đến từng flow xử lý và điều kiện ràng buộc.\n\n"
        )
        return SKILL_SYSTEM_PROMPTS[doc_type] + base

    # Fallback: generic prompt for any unrecognised doc_type
    base = (
        "You are a senior Business Analyst producing enterprise-grade documentation in Vietnamese.\n"
        "Golden rules:\n"
        "- Không bịa business rule. Thiếu thông tin thì ghi 'TBD' và liệt kê câu hỏi cần làm rõ.\n"
        "- Viết rõ ràng, chi tiết, chuyên nghiệp: dùng 'must/shall', tránh 'có thể/should'.\n"
        "- ID nhất quán: BR-01, FR-01, NFR-01, UC-01, VR-01, US-01 (tăng dần).\n"
        "- Output là Markdown, trình bày đầy đủ các phần được yêu cầu.\n"
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
        content = content[:8000]
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
        lines.append("\n**Ghi chú quan trọng:** TOÀN BỘ nội dung viết bằng TIẾNG VIỆT chuyên nghiệp, chi tiết, đầy đủ và có chiều sâu.")
        lines.append("")

    # Add Expert Knowledge (Knowledge Layer)
    expert_knowledge = get_expert_knowledge(doc_type)
    if expert_knowledge:
        lines.append(expert_knowledge)
        lines.append("")

    return "\n".join(lines).strip() + "\n"
