import json

from config.settings import settings


DEFAULT_CONFLUENCE_WORKSPACE_MAP: dict[str, str] = {
    "EEP2": "ws_engineering",
    "AIK": "ws_engineering",
}

DEFAULT_JIRA_WORKSPACE_MAP: dict[str, str] = {
    "ECOS2025": "ws_engineering",
}

DEFAULT_SLACK_WORKSPACE_MAP: dict[str, str] = {
    "general": "ws_general",
    "random": "ws_general",
    "hr-internal": "ws_hr",
    "hr": "ws_hr",
    "finance": "ws_finance",
    "engineering": "ws_engineering",
    "dev": "ws_engineering",
    "tech": "ws_engineering",
    "sales": "ws_sales",
    "management": "ws_management",
}

DEFAULT_SMB_WORKSPACE_MAP: dict[str, str] = {
    "HR": "ws_hr",
    "Finance": "ws_finance",
    "Engineering": "ws_engineering",
    "Sales": "ws_sales",
    "Management": "ws_management",
    "General": "ws_general",
}


def _load_map(raw: str, fallback: dict[str, str]) -> dict[str, str]:
    if not raw.strip():
        return fallback
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return fallback
    if not isinstance(parsed, dict):
        return fallback
    return {str(key): str(value) for key, value in parsed.items()}


DEFAULT_WORKSPACE = settings.DEFAULT_WORKSPACE
CONFLUENCE_WORKSPACE_MAP = _load_map(settings.CONFLUENCE_WORKSPACE_MAP, DEFAULT_CONFLUENCE_WORKSPACE_MAP)
JIRA_WORKSPACE_MAP = _load_map(settings.JIRA_WORKSPACE_MAP, DEFAULT_JIRA_WORKSPACE_MAP)
SLACK_WORKSPACE_MAP = _load_map(settings.SLACK_WORKSPACE_MAP, DEFAULT_SLACK_WORKSPACE_MAP)
SMB_WORKSPACE_MAP = _load_map(settings.SMB_WORKSPACE_MAP, DEFAULT_SMB_WORKSPACE_MAP)


def get_confluence_workspace(space_key: str) -> str:
    return CONFLUENCE_WORKSPACE_MAP.get(space_key, DEFAULT_WORKSPACE)


def get_jira_workspace(project_key: str) -> str:
    return JIRA_WORKSPACE_MAP.get(project_key, DEFAULT_WORKSPACE)


def get_slack_workspace(channel_name: str) -> str:
    if channel_name in SLACK_WORKSPACE_MAP:
        return SLACK_WORKSPACE_MAP[channel_name]
    for key, workspace in SLACK_WORKSPACE_MAP.items():
        if channel_name.startswith(key):
            return workspace
    return DEFAULT_WORKSPACE


def get_smb_workspace(top_folder: str) -> str:
    return SMB_WORKSPACE_MAP.get(top_folder, DEFAULT_WORKSPACE)
