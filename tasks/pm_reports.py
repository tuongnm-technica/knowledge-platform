import asyncio
import json
import uuid
from datetime import datetime
import structlog
from sqlalchemy import text
from bs4 import BeautifulSoup

from connectors.jira.jira_client import JiraClient
from storage.db.db import AsyncSessionLocal
from apps.api.services.connectors_service import get_llm_client
from services.email_service import send_email_async

log = structlog.get_logger()

async def generate_project_report(session, llm, p_key: str) -> str:
    """
    Logic cốt lõi để sinh báo cáo AI cho 1 project và lưu vào DB.
    Trả về nội dung HTML của báo cáo.
    """
    log.info("pm_reports.generate_project_report.started", project=p_key)
    client = JiraClient()
    issues = client.get_issues(p_key, max_results=100)
    if not issues:
        log.warning("pm_reports.generate_project_report.no_issues", project=p_key)
        return ""
        
    in_progress = [i for i in issues if str(i.get("fields", {}).get("status", {}).get("statusCategory", {}).get("key")).lower() in ["in progress", "indeterminate"]]
    
    # Format context for LLM
    context_lines = []
    for idx, issue in enumerate(in_progress[:50]): # limit to 50 active issues
        fields = issue.get("fields", {})
        summary = fields.get("summary", "")
        assignee = fields.get("assignee") or {}
        assignee_name = assignee.get("displayName", "Unassigned")
        status = fields.get("status", {}).get("name", "")
        context_lines.append(f"- [{issue['key']}] {summary} (Assignee: {assignee_name}, Status: {status})")
    
    if not context_lines:
        return ""
        
    prompt = f"""
    You are an expert Project Delivery Manager.
    Review the following active Jira issues for project {p_key}.
    Synthesize a brief executive summary (max 3 short paragraphs) focusing on:
    1. Overall progress feel.
    2. Potential blockers or bottlenecks based on the current workload.
    3. Actionable recommendations.
    
    Data:
    { chr(10).join(context_lines) }
    
    Respond ONLY in Vietnamese, using professional PM terminology. Format your response in HTML (using <b>, <ul>, <li>, <p>). Do not use markdown backticks.
    """
    
    messages = [
        {"role": "system", "content": "You are a helpful AI Project Manager Assistant."},
        {"role": "user", "content": prompt}
    ]
    
    report_html = ""
    try:
        response = await llm.chat(messages, stream=False)
        report_html = response.get("content", "").strip()
        if report_html.startswith("```html"):
            report_html = report_html.replace("```html", "", 1).replace("```", "")
    except Exception as e:
        log.error("pm_reports.llm_failed", project=p_key, error=str(e))
        return ""
    
    # Save to DB
    doc_id = str(uuid.uuid4())
    # Lưu cả bản text (để search/hiển thị snippet) và bản HTML (để hiển thị dashboard/email)
    # Ở đây ta dùng trường content để lưu HTML, và title có chứa project key
    await session.execute(
        text("""
        INSERT INTO doc_drafts (id, doc_type, title, content, created_by, status, created_at, updated_at)
        VALUES (:id, 'pm_risk_report', :title, :content, 'system_pm_job', 'published', NOW(), NOW())
        """),
        {
            "id": doc_id,
            "title": f"Báo cáo rủi ro PM Digest [{p_key}] - {datetime.now().strftime('%Y-%m-%d')}",
            "content": report_html
        }
    )
    return report_html

async def generate_pm_digest(ctx, project_keys: list[str] = None):
    """
    Worker task: Sinh báo cáo AI cho danh sách project.
    """
    try:
        log.info("pm_reports.generate_pm_digest.started")
        client = JiraClient()
        if not project_keys:
            projects = client.get_projects()
            project_keys = [p["key"] for p in projects]
            
        if not project_keys:
            return
            
        llm = await get_llm_client(task_type="agent")
        if not llm:
            return

        async with AsyncSessionLocal() as session:
            for p_key in project_keys:
                await generate_project_report(session, llm, p_key)
            await session.commit()
            log.info("pm_reports.generate_pm_digest.completed")
    except Exception as e:
        log.error("pm_reports.generate_pm_digest.fatal", error=str(e))
        raise

async def send_scheduled_pm_reports(ctx, project_keys: list[str] = None):
    """
    Worker task: Gửi email báo cáo đã có sẵn trong DB (T2, T5).
    """
    try:
        log.info("pm_reports.send_scheduled.started")
        async with AsyncSessionLocal() as session:
            if not project_keys:
                res = await session.execute(text("SELECT DISTINCT metadata->>'project' FROM documents WHERE source='jira'"))
                project_keys = [row[0] for row in res.fetchall() if row[0]]

            # Lấy danh sách email cần gửi
            admin_emails_res = await session.execute(text("SELECT email FROM users WHERE role IN ('pm_po', 'system_admin', 'admin') AND is_active = true"))
            admin_emails = [row[0] for row in admin_emails_res.fetchall() if row[0]]
            if not admin_emails:
                log.warning("pm_reports.send_scheduled.no_recipients")
                return

            for p_key in project_keys:
                # Lấy báo cáo mới nhất từ doc_drafts cho project này
                res = await session.execute(
                    text("""
                    SELECT content, created_at FROM doc_drafts 
                    WHERE doc_type = 'pm_risk_report' AND title LIKE :p_key
                    ORDER BY created_at DESC LIMIT 1
                    """),
                    {"p_key": f"%[{p_key}]%"}
                )
                row = res.mappings().first()
                if not row:
                    continue

                report_html = row["content"]
                created_at = row["created_at"]

                email_body = f"""
                <html>
                <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                    <h2 style="color: #2563eb;">PM Digest - {p_key}</h2>
                    <p style="color: #64748b; font-size: 0.9em;">Phát hành: {created_at.strftime('%d/%m/%Y %H:%M')}</p>
                    <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 20px 0;">
                    {report_html}
                    <br><br>
                    <p style="font-size: 0.85em; color: #94a3b8;">Hệ thống Knowledge Platform - Báo cáo tự động định kỳ.</p>
                </body>
                </html>
                """

                await send_email_async(
                    to_email=admin_emails,
                    subject=f"[Knowledge Platform] Báo cáo dự án {p_key} - {datetime.now().strftime('%d/%m/%Y')}",
                    body=email_body,
                    is_html=True
                )
        log.info("pm_reports.send_scheduled.completed")
    except Exception as e:
        log.error("pm_reports.send_scheduled.failed", error=str(e))
        raise
