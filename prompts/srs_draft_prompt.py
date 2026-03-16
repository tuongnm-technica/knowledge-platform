from __future__ import annotations

from typing import Any


def build_srs_system_prompt() -> str:
    return (
        "You are a senior Business Analyst producing enterprise-grade SRS documents in Vietnamese.\n"
        "Rules:\n"
        "- Không bịa business rule. Thiếu thông tin thì ghi 'TBD' và liệt kê câu hỏi cần làm rõ.\n"
        "- Viết rõ ràng, kiểm thử được: dùng 'must/shall', tránh 'có thể/should'.\n"
        "- ID nhất quán: BR-01, FR-01, NFR-01, UC-01, VR-01 (tăng dần).\n"
        "- Luôn có Traceability: FR ↔ UC ↔ VR (và chừa chỗ TC).\n"
        "- Phân biệt rõ: Functional Requirements vs Non-Functional Requirements.\n"
        "- Nếu có API, mô tả endpoint/params/JSON, lỗi theo RFC 7807 ở mức khái quát.\n"
        "- Output là Markdown.\n"
    )


def build_srs_user_prompt(
    *,
    question: str,
    answer: str,
    sources: list[dict[str, Any]],
    documents: list[dict[str, Any]],
) -> str:
    lines: list[str] = []
    lines.append("Hãy tạo 1 bản nháp SRS theo cấu trúc 10 mục (có Glossary ở đầu), dựa trên thông tin sau.")
    lines.append("")
    if question:
        lines.append("## User request")
        lines.append(question.strip())
        lines.append("")
    if answer:
        lines.append("## Current AI answer (high-level summary)")
        lines.append(answer.strip())
        lines.append("")

    lines.append("## Sources selected (top)")
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
            lines.append("")
            lines.append(content)
            lines.append("")

    lines.append(
        "## Output requirements\n"
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
    )

    return "\n".join(lines).strip() + "\n"
