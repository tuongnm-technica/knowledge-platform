from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from config.settings import settings


log = structlog.get_logger()


async def sync_submitted_drafts(session: AsyncSession, *, limit: int = 50) -> dict:
    """
    Bi-directional sync:
    - Pull Jira issue status for drafts that were submitted.
    - If Jira is Done, mark draft status as 'done'.
    - Store the latest Jira status in suggested_fields (best-effort).
    """
    if not settings.JIRA_URL or not settings.JIRA_API_TOKEN:
        return {"checked": 0, "updated": 0, "skipped": 0, "error": "Jira not configured"}

    result = await session.execute(
        text(
            """
            SELECT id::text AS id, jira_key, suggested_fields, status
            FROM ai_task_drafts
            WHERE status = 'submitted'
              AND jira_key IS NOT NULL
            ORDER BY submitted_at DESC NULLS LAST
            LIMIT :limit
            """
        ),
        {"limit": int(limit)},
    )
    rows = [dict(r) for r in result.mappings().all()]
    if not rows:
        return {"checked": 0, "updated": 0, "skipped": 0}

    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {settings.JIRA_API_TOKEN}",
    }
    base = settings.JIRA_URL.rstrip("/")

    checked = 0
    updated = 0
    skipped = 0

    async with httpx.AsyncClient(timeout=15, verify=settings.JIRA_VERIFY_TLS) as client:
        for row in rows:
            checked += 1
            key = str(row.get("jira_key") or "").strip()
            if not key:
                skipped += 1
                continue

            try:
                resp = await client.get(f"{base}/rest/api/2/issue/{key}", headers=headers, params={"fields": "status"})
                if resp.status_code != 200:
                    # try api v3
                    resp = await client.get(f"{base}/rest/api/3/issue/{key}", headers=headers, params={"fields": "status"})
                if resp.status_code != 200:
                    skipped += 1
                    continue

                data = resp.json() if isinstance(resp.json(), dict) else {}
                fields = data.get("fields") or {}
                status = (fields.get("status") or {}) if isinstance(fields, dict) else {}
                status_name = str(status.get("name") or "").strip()
                status_cat = (status.get("statusCategory") or {}) if isinstance(status, dict) else {}
                cat_key = str(status_cat.get("key") or "").strip().lower()

                done = cat_key == "done" or status_name.lower() in {"done", "closed", "resolved"}

                suggested_fields = row.get("suggested_fields") or {}
                if isinstance(suggested_fields, str):
                    try:
                        suggested_fields = json.loads(suggested_fields) if suggested_fields else {}
                    except Exception:
                        suggested_fields = {}
                if not isinstance(suggested_fields, dict):
                    suggested_fields = {}

                suggested_fields["jira_status"] = status_name
                suggested_fields["jira_status_category"] = cat_key
                suggested_fields["jira_status_checked_at"] = datetime.now(timezone.utc).isoformat()

                await session.execute(
                    text(
                        """
                        UPDATE ai_task_drafts
                        SET suggested_fields = CAST(:sf AS JSON),
                            status = CASE WHEN :done THEN 'done' ELSE status END
                        WHERE id::text = :id AND status = 'submitted'
                        """
                    ),
                    {"sf": json.dumps(suggested_fields), "done": bool(done), "id": row["id"]},
                )

                if done:
                    updated += 1
            except Exception as exc:
                log.warning("jira_sync.issue_failed", jira_key=key, error=str(exc))
                skipped += 1

    await session.commit()
    return {"checked": checked, "updated": updated, "skipped": skipped}

