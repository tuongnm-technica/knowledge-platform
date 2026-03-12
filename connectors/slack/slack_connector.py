import uuid
from datetime import datetime
from models.document import Document, SourceType
from connectors.base.base_connector import BaseConnector
from connectors.slack.slack_client import SlackClient
from connectors.slack.slack_parser import SlackParser
from permissions.workspace_config import get_slack_workspace
from config.settings import settings
import structlog

log = structlog.get_logger()

WINDOW_SIZE = 6


class SlackConnector(BaseConnector):

    def __init__(self):
        self._client = SlackClient()
        self._parser = SlackParser()
    def validate_config(self) -> bool:
        if not settings.SLACK_BOT_TOKEN:
            raise ValueError("SLACK_BOT_TOKEN chưa được cấu hình")
        return True

    async def get_permissions(self, source_id: str) -> list[str]:
        channel_id = source_id.split("_")[0] if "_" in source_id else source_id
        return [f"slack_channel_{channel_id}"]
    
    async def fetch_documents(self) -> list[Document]:

        documents = []
        channels = await self._client.get_channels()

        log.info("slack.fetch.start", total=len(channels))

        for channel in channels:

            channel_id = channel["id"]
            channel_name = channel.get("name", channel_id)
            is_private = channel.get("is_private", False)

            log.info("slack.fetch.channel", name=channel_name)

            try:
                members = await self._client.get_channel_members(channel_id)
                messages = await self._client.get_messages(channel_id, days=90)
            except Exception as e:
                log.warning("slack.channel.failed", channel=channel_name, error=str(e))
                continue

            user_cache = self._client.get_user_cache()

            windows = self._chunk_messages(messages)

            for window in windows:

                content = self._parser.extract_thread_content(
                    window,
                    user_cache=user_cache,
                    channel_name=channel_name
                )

                if not content or len(content) < 20:
                    continue

                doc = Document(
                    id=str(uuid.uuid4()),
                    source=SourceType.SLACK,
                    source_id=f"{channel_id}_{window[0].get('ts','0')}",
                    title=f"[Slack] #{channel_name}",
                    content=content,
                    url=f"https://app.slack.com/client/{channel_id}",
                    author="slack",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow(),
                    metadata={
                        "channel_id": channel_id,
                        "channel_name": channel_name,
                        "message_count": len(window),
                        "members": members,
                        "is_private": is_private,
                    },
                    permissions=[f"slack_channel_{channel_id}"],
                    workspace_id=get_slack_workspace(channel_name),
                )

                documents.append(doc)

            log.info(
                "slack.channel.done",
                channel=channel_name,
                messages=len(messages),
                chunks=len(windows),
            )

        log.info("slack.fetch.done", total=len(documents))
        return documents

    def _chunk_messages(self, messages: list[dict]) -> list[list[dict]]:

        chunks = []

        for i in range(0, len(messages), WINDOW_SIZE):
            window = messages[i:i + WINDOW_SIZE]
            chunks.append(window)

        return chunks