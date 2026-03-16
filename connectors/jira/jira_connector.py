import uuid
from datetime import datetime, timedelta
import asyncio
from models.document import Document, SourceType
from connectors.base.base_connector import BaseConnector
from connectors.jira.jira_client import JiraClient
from permissions.workspace_config import get_jira_workspace  # ← thêm
from config.settings import settings
import structlog

log = structlog.get_logger()


class JiraConnector(BaseConnector):

    def __init__(
        self,
        *,
        project_keys: set[str] | None = None,
        base_url: str | None = None,
        username: str | None = None,
        api_token: str | None = None,
        auth_type: str | None = None,  # token|basic
    ):
        self._base_url = (base_url or settings.JIRA_URL or "").strip()
        self._api_token = (api_token or settings.JIRA_API_TOKEN or "").strip()
        self._username = (username or "").strip() or None
        self._auth_type = (auth_type or ("basic" if self._username else "token")).strip().lower()

        self.validate_config()
        self._client = JiraClient(
            base_url=self._base_url,
            api_token=self._api_token,
            username=self._username,
            auth_type=self._auth_type,
        )
        self._project_keys = {key.strip() for key in (project_keys or set()) if key and str(key).strip()}

    def validate_config(self) -> bool:
        if not self._base_url or not self._api_token:
            raise ValueError("JIRA_URL va JIRA_API_TOKEN chua duoc cau hinh")
        if self._auth_type == "basic" and not self._username:
            raise ValueError("JIRA username/email is required for basic auth")
        return True

    async def fetch_documents(self, last_sync: datetime | None = None) -> list[Document]:
        documents = []
        projects = await asyncio.to_thread(self._client.get_projects)
        log.info("jira.fetch.start", projects=len(projects))

        since = None
        if last_sync:
            # Avoid missing boundary updates due to clock skew / timestamp rounding.
            since = last_sync - timedelta(minutes=2)

        for project in projects:
            project_key  = project["key"]
            if self._project_keys and project_key not in self._project_keys:
                continue
            project_name = project.get("name", project_key)
            log.info("jira.fetch.project", key=project_key, name=project_name)

            if since:
                issues = await asyncio.to_thread(self._client.get_issues_since, project_key, since, 500)
            else:
                issues = await asyncio.to_thread(self._client.get_issues, project_key, 500)
            log.info("jira.fetch.issues", project=project_key, count=len(issues))

            for issue in issues:
                try:
                    doc = self._process_issue(issue, project_key, project_name)
                    if doc:
                        documents.append(doc)
                except Exception as e:
                    log.error("jira.issue.error", issue=issue.get("key"), error=str(e))
                    continue

        log.info("jira.fetch.done", total=len(documents))
        return documents

    def _process_issue(self, issue: dict, project_key: str, project_name: str) -> Document | None:
        fields = issue.get("fields", {}) or {}
        summary = (fields.get("summary") or "No title").strip()

        issue_key = str(issue.get("key") or "").strip()
        issue_type = (fields.get("issuetype") or {}).get("name", "")
        status = (fields.get("status") or {}).get("name", "")
        priority = (fields.get("priority") or {}).get("name", "")
        labels = fields.get("labels") or []
        components = [c.get("name", "") for c in (fields.get("components") or []) if isinstance(c, dict)]
        assignee = (fields.get("assignee") or {}).get("displayName", "") if isinstance(fields.get("assignee"), dict) else ""
        reporter = (fields.get("reporter") or {}).get("displayName", "") if isinstance(fields.get("reporter"), dict) else ""

        description = fields.get("description") or ""
        if isinstance(description, dict):
            description = self._extract_adf_text(description).strip()
        else:
            description = str(description).strip()

        comments_text = self._format_comments(fields.get("comment") or {})

        # Attachments: screenshots/diagrams are critical context (added as placeholders for later vision ingestion).
        image_attachments: list[dict] = []
        for att in (fields.get("attachment") or []):
            if not isinstance(att, dict):
                continue
            mimetype = str(att.get("mimeType") or att.get("mime_type") or "").strip().lower()
            if mimetype and not mimetype.startswith("image/"):
                continue
            att_id = str(att.get("id") or "").strip()
            filename = str(att.get("filename") or att.get("name") or "attachment").strip()
            content_url = str(att.get("content") or "").strip()
            if not (att_id or content_url):
                continue
            image_attachments.append(
                {
                    "id": att_id,
                    "filename": filename,
                    "mime_type": mimetype,
                    "content_url": content_url,
                    "size": int(att.get("size") or 0) or None,
                }
            )

        meta_lines = [
            f"Key: {issue_key}" if issue_key else "",
            f"Project: {project_key} ({project_name})",
            f"Type: {issue_type}" if issue_type else "",
            f"Status: {status}" if status else "",
            f"Priority: {priority}" if priority else "",
            f"Assignee: {assignee}" if assignee else "",
            f"Reporter: {reporter}" if reporter else "",
            f"Labels: {', '.join([str(x) for x in labels if x])}" if labels else "",
            f"Components: {', '.join([c for c in components if c])}" if components else "",
        ]
        meta_block = "\n".join([line for line in meta_lines if line]).strip()

        parts = [summary]
        if meta_block:
            parts.append(meta_block)
        if description:
            parts.append("## Description")
            parts.append(description)
        if comments_text:
            parts.append("## Comments")
            parts.append(comments_text)
        if image_attachments:
            parts.append("## Attachments (images)")
            for att in image_attachments[:20]:
                fid = str(att.get("id") or "").strip()
                fn = str(att.get("filename") or "").strip() or "image"
                if fid:
                    parts.append(f"- {fn} [[JIRA_ATTACHMENT:{fid}]]")
                else:
                    parts.append(f"- {fn} [[JIRA_ATTACHMENT]]")

        content = "\n\n".join([p for p in parts if p and str(p).strip()]).strip()
        if len(content) < 10:
            return None

        permissions  = [f"group_jira_project_{str(project_key or '').strip().lower()}"]
        workspace_id = get_jira_workspace(project_key)  # ← thêm

        doc = Document(
            id=str(uuid.uuid4()),
            source=SourceType.JIRA,
            source_id=issue["id"],
            title=f"[{issue_key}] {summary}" if issue_key else summary,
            content=content,
            url=f"{self._base_url.rstrip('/')}/browse/{issue_key}" if self._base_url else "",
            author=fields.get("creator", {}).get("displayName", "unknown"),
            created_at=self._parse_dt(fields.get("created")),
            updated_at=self._parse_dt(fields.get("updated")),
            metadata={
                "project_key":   project_key,
                "project_name":  project_name,
                "issue_key":     issue_key,
                "status":        fields.get("status", {}).get("name", ""),
                "issue_type":    fields.get("issuetype", {}).get("name", ""),
                "priority":      fields.get("priority", {}).get("name", ""),
                "creator_name":  fields.get("creator", {}).get("displayName", ""),
                "creator_email": fields.get("creator", {}).get("emailAddress", ""),
                "creator_account": fields.get("creator", {}).get("name", "") or fields.get("creator", {}).get("accountId", ""),
                "assignee_name": fields.get("assignee", {}).get("displayName", ""),
                "assignee_email": fields.get("assignee", {}).get("emailAddress", ""),
                "assignee_account": fields.get("assignee", {}).get("name", "") or fields.get("assignee", {}).get("accountId", ""),
                "permission_id": f"group_jira_project_{str(project_key or '').strip().lower()}",
                "comment_count": self._comment_count(fields.get("comment") or {}),
                "image_attachments": image_attachments,
            },
            permissions=permissions,
            workspace_id=workspace_id,  # ← thêm
        )

        log.info("jira.issue.ok", key=issue_key or issue.get("key"), title=summary[:60])
        return doc

    async def get_permissions(self, source_id: str) -> list[str]:
        return [f"group_jira_project_{str(source_id or '').strip().lower()}"]

    def _extract_adf_text(self, adf: dict) -> str:
        """
        Convert Atlassian Document Format (ADF) to readable plain text.
        Keeps newlines and list structure where possible.
        """
        if not isinstance(adf, dict):
            return ""

        node_type = adf.get("type", "")

        if node_type == "text":
            return adf.get("text", "") or ""

        if node_type == "hardBreak":
            return "\n"

        content = adf.get("content") or []
        if not isinstance(content, list):
            content = []

        if node_type in {"paragraph", "heading", "blockquote"}:
            text = "".join(self._extract_adf_text(child) for child in content).strip()
            return f"{text}\n" if text else ""

        if node_type == "codeBlock":
            text = "".join(self._extract_adf_text(child) for child in content).strip()
            return f"```\n{text}\n```\n" if text else ""

        if node_type in {"bulletList", "orderedList"}:
            lines = []
            for item in content:
                item_text = self._extract_adf_text(item).strip()
                if not item_text:
                    continue
                for line in [l for l in item_text.splitlines() if l.strip()]:
                    lines.append(f"- {line.strip()}")
            return "\n".join(lines) + ("\n" if lines else "")

        if node_type == "listItem":
            return "".join(self._extract_adf_text(child) for child in content).strip()

        if node_type == "mention":
            attrs = adf.get("attrs") or {}
            return (attrs.get("text") or attrs.get("displayName") or "").strip()

        return "".join(self._extract_adf_text(child) for child in content)

    def _comment_count(self, comment_field: dict) -> int:
        try:
            return int((comment_field or {}).get("total") or 0)
        except Exception:
            return 0

    def _format_comments(self, comment_field: dict, limit: int = 12) -> str:
        if not isinstance(comment_field, dict):
            return ""

        comments = comment_field.get("comments") or []
        if not isinstance(comments, list) or not comments:
            return ""

        # Prefer newest comments.
        sliced = comments[-limit:]
        lines: list[str] = []
        for c in sliced:
            if not isinstance(c, dict):
                continue
            author = (c.get("author") or {}).get("displayName", "unknown")
            created = str(c.get("created") or "")[:19].replace("T", " ")
            body = c.get("body") or ""
            if isinstance(body, dict):
                body_text = self._extract_adf_text(body).strip()
            else:
                body_text = str(body).strip()
            if not body_text:
                continue
            lines.append(f"[{created}] {author}: {body_text}")

        return "\n".join(lines).strip()

    @staticmethod
    def _parse_dt(s: str) -> datetime:
        if not s:
            return datetime.utcnow()
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt.replace(tzinfo=None)
        except Exception:
            return datetime.utcnow()
