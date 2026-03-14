import uuid
from datetime import datetime
from collections import defaultdict
from models.document import Document, SourceType
from connectors.base.base_connector import BaseConnector
from connectors.slack.slack_client import SlackClient
from connectors.slack.slack_parser import SlackParser
from permissions.workspace_config import get_slack_workspace
from config.settings import settings
import structlog

log = structlog.get_logger()

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
        """
        Gom nhóm tin nhắn Slack theo từng ngày để lưu thành các Document riêng biệt.
        """
        documents = []
        channels = await self._client.get_channels()

        log.info("slack.fetch.start", total_channels=len(channels))

        for channel in channels:
            channel_id = channel["id"]
            channel_name = channel.get("name", channel_id)

            try:
                # Lấy tin nhắn trong 90 ngày (hoặc cấu hình SYNC_DAYS)
                messages = await self._client.get_messages(channel_id, days=90)
                if not messages:
                    continue

                # 1. Gom nhóm tin nhắn theo ngày (YYYY-MM-DD)
                daily_messages = defaultdict(list)
                for msg in messages:
                    ts = float(msg.get("ts", 0))
                    date_key = datetime.fromtimestamp(ts).strftime('%Y-%m-%d')
                    daily_messages[date_key].append(msg)

                user_cache = self._client.get_user_cache()
                members = await self._client.get_channel_members(channel_id)

                # 2. Với mỗi ngày, tạo một Document riêng
                for date_str, msgs in daily_messages.items():
                    # Đảo ngược danh sách tin nhắn để có thứ tự thời gian tăng dần (cũ đến mới)
                    msgs.reverse()
                    
                    content = self._parser.extract_thread_content(
                        msgs,
                        user_cache=user_cache,
                        channel_name=channel_name,
                        date_str=date_str
                    )

                    if not content or len(content.strip()) < 10:
                        continue

                    doc = Document(
                        id=str(uuid.uuid4()),
                        source=SourceType.SLACK,
                        # source_id chứa cả ID channel và ngày để không bị trùng lặp
                        source_id=f"{channel_id}_{date_str}", 
                        title=f"[Slack] #{channel_name} | Ngày {date_str}",
                        content=content,
                        url=f"https://app.slack.com/client/{channel_id}",
                        author="slack",
                        created_at=datetime.strptime(date_str, '%Y-%m-%d'),
                        updated_at=datetime.utcnow(),
                        metadata={
                            "channel_id": channel_id,
                            "channel_name": channel_name,
                            "date": date_str,
                            "message_count": len(msgs),
                            "members": members,
                        },
                        permissions=[f"slack_channel_{channel_id}"],
                        workspace_id=get_slack_workspace(channel_name),
                    )
                    documents.append(doc)

                log.info("slack.channel.done", channel=channel_name, total_days=len(daily_messages))

            except Exception as e:
                log.error("slack.channel.failed", channel=channel_name, error=str(e))
                continue

        log.info("slack.fetch.done", total_documents=len(documents))
        return documents