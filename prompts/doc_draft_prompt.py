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
        "📋 Step 1: Requirement Analyst",
        "Biến idea thô → FR · NFR · BR · Assumptions · Traceability seed",
        "Phân tích yêu cầu",
    ),
    "requirement_review": (
        "🔍 Step 2: Architect Reviewer",
        "Review business logic · Permission model · Edge cases · BR conflicts",
        "Kiến trúc & Review",
    ),
    "solution_design": (
        "🏗️ Step 3: Solution Designer",
        "Architecture + ADR · API contract · Data model · Deployment topology",
        "Giải pháp kỹ thuật",
    ),
    "srs": (
        "📄 Step 4: Document Writer — SRS",
        "SRS 10 mục + Glossary + Traceability Matrix",
        "Tài liệu đặc tả",
    ),
    "brd": (
        "📋 Step 4: Document Writer — BRD",
        "BRD đầy đủ business case (12 or 17-section)",
        "Tài liệu đặc tả",
    ),
    "use_cases": (
        "📐 Step 4: Document Writer — Use Cases",
        "Use Cases chi tiết + FE Technical Notes",
        "Tài liệu đặc tả",
    ),
    "validation_rules": (
        "✅ Step 4: Document Writer — Validation Rules",
        "Validation Rules với UX behavior (FE + BE rules)",
        "Tài liệu đặc tả",
    ),
    "user_stories": (
        "🎯 Step 5: User Story Writer",
        "User Stories · Gherkin AC · INVEST · DoD · Epic→Story→Task",
        "User Story & Task",
    ),
    "fe_spec": (
        "🖥️ Step 6: FE Technical Spec",
        "Component tree · UI State matrix · a11y · Error boundary · Perf budget",
        "Phát triển FE",
    ),
    "qa_test_spec": (
        "🧪 Step 7: QA Reviewer",
        "Test cases (5 levels) · OWASP · UAT exit criteria · Test data strategy",
        "Kiểm thử & QA",
    ),
    "api_spec": (
        "🔌 Step 3: API Spec (Solution Designer)",
        "OpenAPI spec skeleton · RFC 7807 errors · Status codes · Idempotency",
        "Giải pháp kỹ thuật",
    ),
    "deployment_spec": (
        "🚀 Step 8: Deployment Spec",
        "CI/CD · Environment config · Monitoring alerts · Runbook · DR plan",
        "Triển khai & Vận hành",
    ),
    "change_request": (
        "📝 Step 9: Change & Release Mgr — CR",
        "Change Request · Impact Analysis 6 dimensions · Risk · Rollback plan",
        "Thay đổi & Phát hành",
    ),
    "release_notes": (
        "📢 Step 9: Change & Release Mgr — Release Notes",
        "Release Notes: What's new · Improvements · Bug fixes · Rollback",
        "Thay đổi & Phát hành",
    ),
    "function_list": (
        "📊 Step 9: Change & Release Mgr — Function List",
        "Function List: Module/Feature/Function + Status + Links",
        "Thay đổi & Phát hành",
    ),
    "risk_log": (
        "⚠️ Step 9: Change & Release Mgr — Risk Log",
        "Risk Log: Risk-ID · Likelihood · Impact · Mitigation · Owner",
        "Thay đổi & Phát hành",
    ),
}

# Detailed system instructions extracted from mygpt-ba references
# ─────────────────────────────────────────────────────────────────────────────
# reference mapping for Hybrid Edition (20KB+ deep prompts)
# ─────────────────────────────────────────────────────────────────────────────
SKILL_REF_FILES: dict[str, str] = {
    "requirements_intake": "step1-analyst",
    "requirement_review": "step2-reviewer",
    "solution_design": "step3-designer",
    "api_spec": "step3-designer",
    "srs": "step4-writer",
    "brd": "step4-writer",
    "use_cases": "step4-writer",
    "validation_rules": "step4-writer",
    "user_stories": "step5-story-writer",
    "fe_spec": "step6-fe-spec",
    "qa_test_spec": "step7-qa-spec",
    "deployment_spec": "step8-ops-spec",
    "change_request": "step9-change-mgr",
    "release_notes": "step9-change-mgr",
    "function_list": "step9-change-mgr",
    "risk_log": "step9-change-mgr",
}

def get_agent_path(slug: str) -> Path:
    # Works in both local and Docker (/app)
    base = Path(__file__).parent.parent
    return base / "docskill" / "mygpt-ba" / "agents" / slug

def load_full_prompt(doc_type: str) -> str:
    slug = SKILL_REF_FILES.get(doc_type)
    if not slug:
        return ""
    path = get_agent_path(slug) / "gen_prompt.md"
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return ""
    return ""

def load_skill_schema(doc_type: str) -> str:
    slug = SKILL_REF_FILES.get(doc_type)
    if not slug: return ""
    path = get_agent_path(slug) / "schema.json"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""

def load_skill_template(doc_type: str) -> str:
    slug = SKILL_REF_FILES.get(doc_type)
    if not slug: return ""
    path = get_agent_path(slug) / "human_template.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""

# Initialize with full prompts from filesystem
SKILL_SYSTEM_PROMPTS: dict[str, str] = {
    doc_type: load_full_prompt(doc_type)
    for doc_type in SKILL_REF_FILES
}

# Map doc_type → agent label for display in UI
SKILL_DOC_TYPE_GROUPS: dict[str, list[str]] = {
    "Phân tích yêu cầu": ["requirements_intake"],
    "Kiến trúc & Review": ["requirement_review"],
    "Giải pháp kỹ thuật": ["solution_design", "api_spec"],
    "Tài liệu đặc tả": ["srs", "brd", "use_cases", "validation_rules"],
    "User Story & Task": ["user_stories"],
    "Phát triển FE": ["fe_spec"],
    "Kiểm thử & QA": ["qa_test_spec"],
    "Triển khai & Vận hành": ["deployment_spec"],
    "Thay đổi & Phát hành": ["change_request", "release_notes", "function_list", "risk_log"],
}

PROMPT_EXTENSIONS: dict[str, str] = {
    "api_spec": "Tạo API Specification: endpoints, params, request/response JSON examples, error model (RFC 7807), status codes.\n",
    "requirements_intake": "Tạo Requirements Intake: trích xuất danh sách BR/FR/NFR nguyên tử (atomic) từ đầu vào. Nếu dữ liệu thiếu, hãy điền 'TBD' và gợi ý các câu hỏi làm rõ. TUYỆT ĐỐI KHÔNG tự sáng tác nghiệp vụ (No Hallucination).\n",
    "requirement_review": "Review requirement: Tìm lỗi logic và mâu thuẫn (Gaps/Conflicts/Risks). Trong phần này, bạn ĐƯỢC PHÉP đưa ra nhận xét (Feedback) và đánh giá Vergeict (BLOCK/WARN/OK). Lưu ý: Chỉ thực hiện Review khi doc_type là 'requirement_review'.\n",
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
        "- Proactive Questions (Câu hỏi gợi mở): Suy luận từ ngữ cảnh để hỏi các câu hỏi giúp lấp đầy khoảng trống nghiệp vụ.\n"
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
        
    return (
        "\n\n--- BEGIN EXPERT STANDARDS (FOR FORMATTING & QUALITY ONLY) ---\n"
        "## <STANDARDS_GUIDELINES>\n"
        "### [QUY ĐỊNH CỦA HỆ THỐNG - KHÔNG PHẢI NGHIỆP VỤ CỦA KHÁCH HÀNG]\n"
        "Sử dụng các tiêu chuẩn sau đây CHỈ để định hướng cấu trúc, văn phong và kiểm soát chất lượng.\n"
        "CẢNH BÁO TỐI CAO: TUYỆT ĐỐI KHÔNG lấy các ví dụ (như ATRS, RAG, AI, Auth) "
        "để áp dụng vào nội dung yêu cầu của khách hàng. Hãy coi chúng là 'giả định' chỉ dành cho việc minh họa template.\n\n"
        + "\n\n".join(knowledge_blocks)
        + "\n</STANDARDS_GUIDELINES>\n"
        "--- END EXPERT STANDARDS ---\n\n"
    )


STRICT_ISOLATION_RULES = """
STRICT CONTEXT ISOLATION & PERSONA RULES:
1. NO FABRICATION: Never invent business rules, functional details, or technical specs. If a field lacks input, write 'TBD' and add a question in 'Clarification Questions'.
2. STANDARDS ARE NOT INPUTS: Documents in <STANDARDS_GUIDELINES> are ONLY for formatting. If they mention 'ATRS' or 'RAG' and your input does NOT, you must NOT mention them.
3. PERSONA LOCK: 
   - If doc_type is NOT 'requirement_review', do NOT provide 'Feedback' or 'Review' comments. Just produce the structured document.
   - You are a WRITER by default. You only become a REVIEWER when explicitly requested.
4. MULTI-SOURCE SYNTHESIS: Reconstruct facts only from <USER_REQUEST> and <SELECTED_SOURCES>. If sources conflict, state the conflict clearly using source citations [SRC-N].
5. IF THE INPUT IS EMPTY: Output only the template structure with all values as 'TBD' + 'Clarification Questions'. Do NOT use template examples to fill the document.
"""

def build_doc_system_prompt(*, doc_type: str, db_prompt: str | None = None) -> str:
    doc_type = (doc_type or "srs").strip().lower()

    # Highest priority: user-customized prompt stored in DB
    if db_prompt and db_prompt.strip():
        base = (
            f"{STRICT_ISOLATION_RULES}\n"
            "Yêu cầu quan trọng nhất: TOÀN BỘ nội dung tài liệu phải được viết bằng TIẾNG VIỆT chuyên nghiệp, giàu thông tin, không trình bày chung chung.\n"
            "ID nhất quán: BR-01, FR-01, NFR-01, UC-01, VR-01, US-01 (tăng dần xuyên suốt).\n"
            "Output phải là Markdown đầy đủ, phân tích sâu các khía cạnh nghiệp vụ và kỹ thuật.\n\n"
        )
        return db_prompt.strip() + "\n\n" + base

    # Second priority: hardcoded mygpt-ba skill prompt
    if doc_type in SKILL_SYSTEM_PROMPTS:
        base = (
            f"{STRICT_ISOLATION_RULES}\n"
            "Yêu cầu quan trọng nhất: TOÀN BỘ nội dung tài liệu phải được viết bằng TIẾNG VIỆT chuyên nghiệp, giàu thông tin, phân tích đa chiều, tránh viết ngắn gọn hời hợt.\n"
            "ID nhất quán: BR-01, FR-01, NFR-01, UC-01, VR-01, US-01 (tăng dần xuyên suốt).\n"
            "Output phải là Markdown đầy đủ, chi tiết đến từng flow xử lý và điều kiện ràng buộc.\n\n"
        )
        return SKILL_SYSTEM_PROMPTS[doc_type] + base

    # Fallback: generic prompt for any unrecognised doc_type
    base = (
        "You are a senior Business Analyst producing enterprise-grade documentation in Vietnamese.\n"
        f"{STRICT_ISOLATION_RULES}\n"
        "Golden rules:\n"
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
    previous_drafts: list[dict[str, Any]] | None = None,
) -> str:
    doc_type = (doc_type or "srs").strip().lower()
    label = SUPPORTED_DOC_TYPES.get(doc_type, doc_type)

    lines: list[str] = []
    lines.append(f"Hãy tạo tài liệu dạng **{label}** dựa trên thông tin sau.")
    lines.append("")
    if question:
        lines.append("<USER_REQUEST>")
        lines.append(str(question).strip())
        lines.append("</USER_REQUEST>")
        lines.append("")
    if answer:
        lines.append("<CURRENT_AI_INSIGHT>")
        lines.append(str(answer).strip())
        lines.append("</CURRENT_AI_INSIGHT>")
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

    # Dynamic Truncation Logic based on document count
    doc_list = documents or []
    doc_count = len(doc_list)
    
    if doc_count <= 2:
        char_limit = 6000
    elif doc_count <= 5:
        char_limit = 3500
    elif doc_count <= 8:
        char_limit = 2000
    else:
        char_limit = 1200

    lines.append(f"<SELECTED_SOURCES count={doc_count} limit={char_limit}chars_per_doc>")
    
    for d in doc_list[:8]:
        title = str(d.get("title") or "").strip() or "Untitled"
        source = str(d.get("source") or "").strip()
        url = str(d.get("url") or "").strip()
        updated = str(d.get("updated_at") or "").strip()
        content = str(d.get("content") or "").strip()
        
        # Apply dynamic truncation
        content = content[:char_limit]
        
        lines.append(f"### [Source: {source}] {title}")
        if url:
            lines.append(f"- url: {url}")
        if content:
            lines.append("<content>")
            lines.append(content)
            lines.append("</content>\n")

    lines.append("</SELECTED_SOURCES>")

    # Add Previous Drafts (Internal Context)
    if previous_drafts:
        lines.append(f"\n<INTERNAL_WORKING_DRAFTS count={len(previous_drafts)}>")
        lines.append("These are recent drafts related to this project. Use them to maintain consistency and context.")
        for d in previous_drafts[:5]:
            d_title = str(d.get("title") or "Untitled").strip()
            d_type = str(d.get("doc_type") or "unknown").strip()
            d_content = str(d.get("content") or "").strip()
            lines.append(f"### [DRAFT: {d_type}] {d_title}")
            lines.append("<content>")
            lines.append(d_content[:4000]) # Protect context window
            lines.append("</content>\n")
        lines.append("</INTERNAL_WORKING_DRAFTS>\n")

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
