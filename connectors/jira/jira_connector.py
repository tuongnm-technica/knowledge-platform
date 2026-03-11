import uuid
from datetime import datetime
from models.document import Document, SourceType
from connectors.base.base_connector import BaseConnector
from connectors.jira.jira_client import JiraClient
from permissions.workspace_config import get_jira_workspace  # ← thêm
from config.settings import settings
import structlog

log = structlog.get_logger()


class JiraConnector(BaseConnector):

    def __init__(self):
        self.validate_config()
        self._client = JiraClient()

    def validate_config(self) -> bool:
        if not all([settings.JIRA_URL, settings.JIRA_API_TOKEN]):
            raise ValueError("JIRA_URL và JIRA_API_TOKEN chưa được cấu hình")
        return True

    async def fetch_documents(self) -> list[Document]:
        documents = []
        projects = self._client.get_projects()
        log.info("jira.fetch.start", projects=len(projects))

        for project in projects:
            project_key  = project["key"]
            project_name = project.get("name", project_key)
            log.info("jira.fetch.project", key=project_key, name=project_name)

            issues = self._client.get_issues(project_key, max_results=200)
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
        fields  = issue.get("fields", {})
        summary = fields.get("summary", "No title")

        description = fields.get("description") or ""
        if isinstance(description, dict):
            description = self._extract_adf_text(description)

        content = f"{summary}\n\n{description}".strip()
        if len(content) < 10:
            return None

        permissions  = [f"jira_project_{project_key}"]
        workspace_id = get_jira_workspace(project_key)  # ← thêm

        doc = Document(
            id=str(uuid.uuid4()),
            source=SourceType.JIRA,
            source_id=issue["id"],
            title=f"[{issue['key']}] {summary}",
            content=content,
            url=f"{settings.JIRA_URL.rstrip('/')}/browse/{issue['key']}",
            author=fields.get("creator", {}).get("displayName", "unknown"),
            created_at=self._parse_dt(fields.get("created")),
            updated_at=self._parse_dt(fields.get("updated")),
            metadata={
                "project_key":   project_key,
                "project_name":  project_name,
                "issue_key":     issue["key"],
                "status":        fields.get("status", {}).get("name", ""),
                "issue_type":    fields.get("issuetype", {}).get("name", ""),
                "priority":      fields.get("priority", {}).get("name", ""),
                "permission_id": f"jira_project_{project_key}",
            },
            permissions=permissions,
            workspace_id=workspace_id,  # ← thêm
        )

        log.info("jira.issue.ok", key=issue["key"], title=summary[:60])
        return doc

    async def get_permissions(self, source_id: str) -> list[str]:
        return [f"jira_project_{source_id}"]

    def _extract_adf_text(self, adf: dict) -> str:
        texts = []
        if isinstance(adf, dict):
            if adf.get("type") == "text":
                texts.append(adf.get("text", ""))
            for child in adf.get("content", []):
                texts.append(self._extract_adf_text(child))
        return " ".join(t for t in texts if t)

    @staticmethod
    def _parse_dt(s: str) -> datetime:
        if not s:
            return datetime.utcnow()
        try:
            dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
            return dt.replace(tzinfo=None)
        except Exception:
            return datetime.utcnow()