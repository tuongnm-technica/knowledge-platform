# ══════════════════════════════════════════════════════════════
# permissions/workspace_config.py
# Mapping: source key → workspace_id
# ══════════════════════════════════════════════════════════════

DEFAULT_WORKSPACE = "ws_general"

# ─── Confluence spaces ────────────────────────────────────────
CONFLUENCE_WORKSPACE_MAP: dict[str, str] = {
    "EEP2": "ws_engineering",
    "AIK":  "ws_engineering",
}

# ─── Jira projects ────────────────────────────────────────────
JIRA_WORKSPACE_MAP: dict[str, str] = {
    "ECOS2025": "ws_engineering",
}

# ─── Slack channels (theo tên channel) ───────────────────────
SLACK_WORKSPACE_MAP: dict[str, str] = {
    "general":       "ws_general",
    "random":        "ws_general",
    "hr-internal":   "ws_hr",
    "hr":            "ws_hr",
    "finance":       "ws_finance",
    "engineering":   "ws_engineering",
    "dev":           "ws_engineering",
    "tech":          "ws_engineering",
    "sales":         "ws_sales",
    "management":    "ws_management",
    'C0936S9HN5A':   "ws_general",  # test-team-ăn-chơi
}

# ─── SMB top-level folders ────────────────────────────────────
SMB_WORKSPACE_MAP: dict[str, str] = {
    "HR":          "ws_hr",
    "Finance":     "ws_finance",
    "Engineering": "ws_engineering",
    "Sales":       "ws_sales",
    "Management":  "ws_management",
    "General":     "ws_general",
}


# ─── Helper functions ─────────────────────────────────────────
def get_confluence_workspace(space_key: str) -> str:
    return CONFLUENCE_WORKSPACE_MAP.get(space_key, DEFAULT_WORKSPACE)


def get_jira_workspace(project_key: str) -> str:
    return JIRA_WORKSPACE_MAP.get(project_key, DEFAULT_WORKSPACE)


def get_slack_workspace(channel_name: str) -> str:
    # Tìm exact match trước
    if channel_name in SLACK_WORKSPACE_MAP:
        return SLACK_WORKSPACE_MAP[channel_name]
    # Tìm theo prefix: "hr-announcements" → ws_hr
    for key, workspace in SLACK_WORKSPACE_MAP.items():
        if channel_name.startswith(key):
            return workspace
    return DEFAULT_WORKSPACE


def get_smb_workspace(top_folder: str) -> str:
    return SMB_WORKSPACE_MAP.get(top_folder, DEFAULT_WORKSPACE)