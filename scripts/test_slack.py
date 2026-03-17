import sys
import asyncio
sys.path.insert(0, ".")


async def test():
    from connectors.slack.slack_client import SlackClient

    client = SlackClient()

    print("Testing Slack connection...")

    # Test public channels
    channels = await client.get_channels()
    print(f"\n✅ Found {len(channels)} channels:")
    for c in channels[:10]:
        print(f"  - #{c.get('name')} ({'private' if c.get('is_private') else 'public'})")


asyncio.run(test())