from atlassian import Jira
from config.settings import settings
from datetime import datetime
import structlog

log = structlog.get_logger()

ALLOWED_PROJECT_KEYS = ["ECOS2025"]


class JiraClient:
    def __init__(self):
        if not all([settings.JIRA_URL, settings.JIRA_API_TOKEN]):
            raise ValueError("JIRA_URL và JIRA_API_TOKEN chưa được cấu hình")

        self._client = Jira(
            url=settings.JIRA_URL,
            token=settings.JIRA_API_TOKEN,
            cloud=False,
        )

    def get_projects(self) -> list[dict]:
        try:
            projects = self._client.projects()
            if ALLOWED_PROJECT_KEYS:
                projects = [p for p in projects if p["key"] in ALLOWED_PROJECT_KEYS]
            return projects
        except Exception as e:
            log.error("jira.get_projects.failed", error=str(e))
            return []

    def get_issues(self, project_key: str, max_results: int = 500) -> list[dict]:
        """Full sync — lấy tất cả issues."""
        try:
            jql    = f"project = {project_key} ORDER BY updated DESC"
            result = self._client.jql(jql, limit=max_results)
            return result.get("issues", [])
        except Exception as e:
            log.error("jira.get_issues.failed", project=project_key, error=str(e))
            return []

    def get_issues_since(self, project_key: str, since: datetime, max_results: int = 500) -> list[dict]:
        """
        Incremental sync — chỉ lấy issues updated SAU thời điểm since.
        Jira JQL format: updated > "yyyy/MM/dd HH:mm"
        """
        try:
            since_str = since.strftime("%Y/%m/%d %H:%M")
            jql = f'project = {project_key} AND updated > "{since_str}" ORDER BY updated ASC'
            log.info("jira.get_issues_since", project=project_key, since=since_str)

            result = self._client.jql(jql, limit=max_results)
            issues = result.get("issues", [])
            log.info("jira.incremental.found", project=project_key, count=len(issues))
            return issues

        except Exception as e:
            log.error("jira.get_issues_since.failed", project=project_key, error=str(e))
            log.warning("jira.fallback_to_full_sync", project=project_key)
            return self.get_issues(project_key, max_results=max_results)

    def test_connection(self) -> bool:
        try:
            self._client.projects()
            return True
        except Exception as e:
            log.error("jira.test_connection.failed", error=str(e))
            return False