from atlassian import Jira
from config.settings import settings
import structlog

log = structlog.get_logger()


class JiraClient:
    def __init__(self):
        if not all([settings.JIRA_URL, settings.JIRA_USERNAME, settings.JIRA_API_TOKEN]):
            raise ValueError("JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN chưa đủ")
        self._client = Jira(
            url=settings.JIRA_URL,
            username=settings.JIRA_USERNAME,
            password=settings.JIRA_API_TOKEN,
            cloud=True,
        )

    def get_projects(self) -> list[dict]:
        try:
            return self._client.projects()
        except Exception as e:
            log.error("jira.get_projects.failed", error=str(e))
            return []

    def get_issues(self, project_key: str, max_results: int = 100) -> list[dict]:
        try:
            jql = f"project = {project_key} ORDER BY updated DESC"
            result = self._client.jql(jql, limit=max_results)
            return result.get("issues", [])
        except Exception as e:
            log.error("jira.get_issues.failed", project=project_key, error=str(e))
            return []