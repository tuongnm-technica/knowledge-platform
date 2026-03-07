import uuid
from datetime import datetime
from models.document import Document, SourceType
from connectors.base.base_connector import BaseConnector
from connectors.jira.jira_client import JiraClient
from config.settings import settings
import structlog

log = structlog.get_logger()


class JiraConnector(BaseConnector):
    def __init__(self):
        self.validate_config()
        self._client = JiraClient()

    def validate_config(self) -> bool:
        if not all([settings.JIRA_URL, settings.JIRA_USERNAME, settings.JIRA_API_TOKEN]):
            raise ValueError("Jira credentials chưa đầy đủ")
        return True

    async def fetch_documents(self) -> list[Document]:
        documents = []
        projects = self._client.get_projects()

        for project in projects:
            project_key = project["key"]
            log.info("jira.fetch.project", project=project_key)
            issues = self._client.get_issues(project_key)

            for issue in issues:
                fields = issue.get("fields", {})
                summary = fields.get("summary", "No title")
                description = fields.get("description") or ""

                if isinstance(description, dict):
                    description = self._extract_adf_text(description)

                content = f"{summary}\n\n{description}".strip()
                if len(content) < 10:
                    continue

                permissions = await self.get_permissions(project_key)

                def parse_dt(s):
                    if not s:
                        return datetime.utcnow()
                    try:
                        return datetime.fromisoformat(s.replace("Z", "+00:00"))
                    except Exception:
                        return datetime.utcnow()

                doc = Document(
                    id=str(uuid.uuid4()),
                    source=SourceType.JIRA,
                    source_id=issue["id"],
                    title=f"[{issue['key']}] {summary}",
                    content=content,
                    url=f"{settings.JIRA_URL}/browse/{issue['key']}",
                    author=fields.get("creator", {}).get("displayName", "unknown"),
                    created_at=parse_dt(fields.get("created")),
                    updated_at=parse_dt(fields.get("updated")),
                    metadata={
                        "project": project_key,
                        "issue_key": issue["key"],
                        "status": fields.get("status", {}).get("name", ""),
                        "issue_type": fields.get("issuetype", {}).get("name", ""),
                        "priority": fields.get("priority", {}).get("name", ""),
                    },
                    permissions=permissions,
                )
                documents.append(doc)

        log.info("jira.fetch.done", total=len(documents))
        return documents

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