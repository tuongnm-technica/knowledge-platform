from atlassian import Jira
from config.settings import settings
import structlog

log = structlog.get_logger()

# Chỉ sync những projects này
ALLOWED_PROJECT_KEYS = [
    "ECOS2025",  
    # Thêm project keys muốn sync
    # "KP",
]


class JiraClient:
    def __init__(self):
        if not all([settings.JIRA_URL, settings.JIRA_API_TOKEN]):
            raise ValueError("JIRA_URL và JIRA_API_TOKEN chưa được cấu hình")

        self._client = Jira(
            url=settings.JIRA_URL,
            token=settings.JIRA_API_TOKEN,  # Personal Access Token
            cloud=False,                     # Server/Data Center
            timeout = 180,
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

    def get_issues(self, project_key: str, max_results: int = 100) -> list[dict]:
        try:
            jql = f"project = {project_key} ORDER BY updated DESC"
            result = self._client.jql(jql, limit=max_results)
            return result.get("issues", [])
        except Exception as e:
            log.error("jira.get_issues.failed", project=project_key, error=str(e))
            return []

    def test_connection(self) -> bool:
        try:
            self._client.projects()
            return True
        except Exception as e:
            log.error("jira.test_connection.failed", error=str(e))
            return False