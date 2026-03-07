import uuid
from datetime import datetime
from models.document import Document, SourceType
from connectors.base.base_connector import BaseConnector
from connectors.slack.slack_client import SlackClient
from connectors.slack.slack_parser import SlackParser
from connectors.slack.slack_permissions import SlackPermissions
from config.settings import settings
import structlog

log = structlog.get_logger()


class SlackConnector(BaseConnector):
    def __init__(self):
        self.validate_config()
        self._client = SlackClient()
        self._parser = SlackParser()
        self._permissions = SlackPermissions(self._client)

    def validate_config(self) -> bool:
        if not settings.SLACK_BOT_TOKEN:
            raise ValueError("SLACK_BOT_TOKEN chưa được cấu hình")
        return True

    async def fetch_documents(self) -> list[Document]:
        documents = []
        channels = await self._client.get_channels()

        for channel in channels:
            channel_id = channel["id"]
            channel_name = channel.get("name", channel_id)
            log.info("slack.fetch.channel", channel=channel_name)

            messages = await self._client.get_messages(channel_id)
            permissions = await self.get_permissions(channel_id)

            for msg in messages:
                text = self._parser.parse_message(msg)
                if not text or len(text) < 10:
                    continue

                ts = msg.get("ts", "0")
                created = datetime.fromtimestamp(float(ts))

                doc = Document(
                    id=str(uuid.uuid4()),
                    source=SourceType.SLACK,
                    source_id=f"{channel_id}_{ts}",
                    title=f"#{channel_name} — {created.strftime('%Y-%m-%d %H:%M')}",
                    content=text,
                    url=f"https://slack.com/archives/{channel_id}/p{ts.replace('.', '')}",
                    author=msg.get("user", "unknown"),
                    created_at=created,
                    updated_at=created,
                    metadata={"channel": channel_name, "channel_id": channel_id},
                    permissions=permissions,
                )
                documents.append(doc)

        log.info("slack.fetch.done", total=len(documents))
        return documents

    async def get_permissions(self, source_id: str) -> list[str]:
        return await self._permissions.get_permitted_groups(source_id)