from connectors.slack.slack_client import SlackClient


class SlackPermissions:
    def __init__(self, client: SlackClient):
        self._client = client

    async def get_permitted_groups(self, channel_id: str) -> list[str]:
        members = await self._client.get_channel_members(channel_id)
        groups = [f"slack_channel_{channel_id}"]
        for member_id in members:
            groups.append(f"slack_user_{member_id}")
        return groups