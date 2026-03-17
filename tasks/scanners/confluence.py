from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
import structlog

from config.settings import settings
from connectors.confluence.confluence_client import ConfluenceClient
from connectors.confluence.confluence_parser import ConfluenceParser
from tasks.extractor import extract_tasks_from_content
from utils.vision import describe_images_batch
from .base import BaseScanner

log = structlog.get_logger()


class ConfluenceScanner(BaseScanner):
    
    async def scan(self, days_back: int, triggered_by: str, created_by: str | None) -> int:
        if not settings.CONFLUENCE_URL or not settings.CONFLUENCE_API_TOKEN:
            log.warning("scanner.confluence.no_config")
            return 0

        total = 0
        selection = await self._load_connector_selection("confluence")
        selected_spaces = set([str(x) for x in (selection.get("spaces") or [])]) if isinstance(selection, dict) else set()

        conf_client = ConfluenceClient()
        parser = ConfluenceParser()

        since_dt = datetime.now(timezone.utc) - timedelta(days=days_back)
        configured_spaces = selected_spaces or set(self._csv_values(settings.CONFLUENCE_SPACE_KEYS))

        spaces = conf_client.get_spaces()
        space_keys = [s.get("key") for s in spaces if s.get("key")]
        if configured_spaces:
            space_keys = [k for k in space_keys if k in configured_spaces]

        for space_key in space_keys:
            pages = await asyncio.to_thread(conf_client.get_pages_since, space_key, since_dt, 200)
            for page in pages:
                page_id = str(page.get("id") or "").strip()
                if not page_id: continue

                page_title = str(page.get("title") or "").strip()
                body_html = await asyncio.to_thread(conf_client.get_page_body, page_id)
                clean = parser.parse(body_html)

                if not clean or len(clean.strip()) < 120:
                    continue

                if settings.VISION_ENABLED and str(settings.OLLAMA_VISION_MODEL or "").strip():
                    try:
                        wanted = list(dict.fromkeys([str(x).strip() for x in re.findall(r"\[\[IMAGE:([^\]]+)\]\]", clean or "") if str(x).strip()]))[:2]
                        if wanted:
                            atts = await asyncio.to_thread(conf_client.list_attachments, page_id, 200)
                            by_name = {str(a.get("filename") or "").strip().lower(): a for a in (atts or []) if isinstance(a, dict)}
                            fetched = [{"image_bytes": await asyncio.to_thread(conf_client.download_attachment, dl), "hint": page_title} for fn in wanted if (it := by_name.get(fn.lower())) and (dl := str(it.get("download_url") or "").strip())]
                            if fetched:
                                caps = await describe_images_batch([f for f in fetched if f.get("image_bytes")], concurrency=2)
                                cap_lines = [c.strip() for c in caps if str(c or "").strip()]
                                if cap_lines:
                                    clean = (clean + "\n\n## Images\n" + "\n".join([f"- {c}" for c in cap_lines])).strip()
                    except Exception:
                        pass

                base = (settings.CONFLUENCE_URL or "").rstrip("/")
                web_ui = (page.get("_links") or {}).get("webui", "") if isinstance(page, dict) else ""
                wiki_prefix = "/wiki" if isinstance(web_ui, str) and web_ui.startswith("/spaces/") and not base.endswith("/wiki") else ""
                stable_url = f"{base}{wiki_prefix}/pages/viewpage.action?pageId={page_id}" if base else ""

                tasks = await extract_tasks_from_content(content=clean, source_type="confluence", llm_client=self.llm_client, source_ref=page_id)

                for task in tasks:
                    suggested_assignee = task.suggested_assignee or await self.repo.suggest_assignee_from_history(labels=task.labels or [])
                    draft_id = await self.repo.create_draft(
                        title=task.title,
                        description=task.description,
                        source_type="confluence",
                        source_ref=page_id,
                        source_summary=f"[{page_title}] {clean[:300]}",
                        source_url=stable_url or None,
                        scope_group_id=f"group_confluence_space_{str(space_key or '').strip().lower()}",
                        source_meta={"space_key": space_key, "page_id": page_id, "title": page_title, "stable_url": stable_url, "evidence": (task.evidence or "").strip() or clean[:260]},
                        evidence=[{"source": "confluence", "url": stable_url, "quote": (task.evidence or "").strip() or clean[:360], "ref": {"space_key": space_key, "page_id": page_id}}],
                        issue_type=self._suggest_issue_type_from_labels(task.labels),
                        epic_key=self._detect_epic_key(f"{task.title}\n{task.description}\n{page_title}"),
                        suggested_assignee=suggested_assignee,
                        priority=task.priority, labels=task.labels, triggered_by=triggered_by, created_by=created_by,
                    )
                    if draft_id: total += 1
        return total