from datetime import datetime

import structlog
from atlassian import Jira

from config.settings import settings


log = structlog.get_logger()


def _allowed_project_keys() -> set[str]:
    raw = (settings.JIRA_PROJECT_KEYS or "").strip()
    if not raw:
        return set()
    return {key.strip() for key in raw.split(",") if key.strip()}


class JiraClient:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_token: str | None = None,
        username: str | None = None,
        auth_type: str | None = None,  # token|basic
        cloud: bool | None = None,
    ):
        url = (base_url or settings.JIRA_URL or "").strip()
        token = (api_token or settings.JIRA_API_TOKEN or "").strip()
        auth_type = (auth_type or "token").strip().lower()
        cloud_flag = bool(getattr(settings, "JIRA_CLOUD", False))
        if cloud is not None:
            cloud_flag = bool(cloud)

        if not url or not token:
            raise ValueError("JIRA_URL va JIRA_API_TOKEN chua duoc cau hinh")

        if auth_type == "basic":
            user = (username or "").strip()
            if not user:
                raise ValueError("JIRA username/email is required for basic auth")
            self._client = Jira(
                url=url,
                username=user,
                password=token,
                cloud=cloud_flag,
            )
        else:
            self._client = Jira(
                url=url,
                token=token,
                cloud=cloud_flag,
            )

    @staticmethod
    def _fields() -> list[str]:
        # Keep payload lean but RAG-friendly.
        return [
            "summary",
            "description",
            "status",
            "issuetype",
            "priority",
            "creator",
            "reporter",
            "assignee",
            "labels",
            "components",
            "project",
            "created",
            "updated",
            "comment",
            "attachment",
        ]

    def get_projects(self, filter_allowed: bool = False) -> list[dict]:
        """Return all Jira projects the token can see.

        `filter_allowed` is kept for backward-compat but defaults to False:
        project filtering is the responsibility of `JiraConnector` via
        `connector_configs.selection.projects` (stored in DB).  Relying on
        the env-var JIRA_PROJECT_KEYS as a secondary filter caused the
        connector to silently skip all projects not in that env list.
        """
        try:
            projects = self._client.projects()
            if filter_allowed:
                allowed_project_keys = _allowed_project_keys()
                if allowed_project_keys:
                    projects = [project for project in projects if project["key"] in allowed_project_keys]
            return projects
        except Exception as exc:
            log.error("jira.get_projects.failed", error=str(exc))
            return []

    def get_issues(self, project_key: str, max_results: int = 500) -> list[dict]:
        try:
            return self._jql_issues(
                f"project = {project_key} ORDER BY updated DESC",
                max_results=max_results,
            )
        except Exception as exc:
            log.error("jira.get_issues.failed", project=project_key, error=str(exc))
            return []

    def get_issues_since(self, project_key: str, since: datetime, max_results: int = 500) -> list[dict]:
        try:
            since_str = since.strftime("%Y/%m/%d %H:%M")
            issues = self._jql_issues(
                f'project = {project_key} AND updated >= "{since_str}" ORDER BY updated ASC',
                max_results=max_results,
            )
            log.info("jira.incremental.found", project=project_key, since=since_str, count=len(issues))
            return issues
        except Exception as exc:
            log.error("jira.get_issues_since.failed", project=project_key, error=str(exc))
            log.warning("jira.fallback_to_full_sync", project=project_key)
            return self.get_issues(project_key, max_results=max_results)

    def _jql_issues(self, jql: str, *, max_results: int) -> list[dict]:
        """Paginate through JQL results, capped at *max_results*."""
        start = 0
        issues: list[dict] = []
        # Use page size of 100 — large enough for throughput, small enough to
        # avoid Jira's payload-size limit on instances with heavy custom fields.
        limit = min(max_results, 100) if max_results else 100

        while True:
            result = self._client.jql(
                jql,
                fields=self._fields(),
                start=start,
                limit=limit,
            )
            batch = result.get("issues", []) if isinstance(result, dict) else []
            if not batch:
                break

            issues.extend(batch)
            log.debug("jira.page", jql=jql[:80], start=start, batch=len(batch), total_so_far=len(issues))

            if max_results and len(issues) >= max_results:
                issues = issues[:max_results]
                break

            total = int(result.get("total") or 0)
            start += len(batch)
            if total and start >= total:
                break
            if len(batch) < limit:
                break

        return issues

    def test_connection(self) -> bool:
        try:
            self._client.projects()
            return True
        except Exception as exc:
            log.error("jira.test_connection.failed", error=str(exc))
            return False
