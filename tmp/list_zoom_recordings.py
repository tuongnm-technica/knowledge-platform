import asyncio
from connectors.zoom.zoom_client import ZoomClient
from datetime import datetime, timedelta

ACCOUNT_ID = "JHteZboYTE-6yTrbD6XG4g"
CLIENT_ID = "eWjnDm7YR7iYgAQu1xqKgw"
CLIENT_SECRET = "YR9EvnKlviZT2bv4YthMV1zVPL878sL4"

async def debug():
    client = ZoomClient(
        account_id=ACCOUNT_ID,
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET
    )
    
    # Try a wider range: 180 days
    from_date = (datetime.utcnow() - timedelta(days=180)).strftime("%Y-%m-%d")
    print(f"Checking recordings from {from_date}...")
    
    try:
        recordings = await client.list_recordings(from_date=from_date)
        print(f"Found {len(recordings)} recordings.")
        for r in recordings:
            print(f" - [{r.get('id')}] {r.get('topic')} ({r.get('start_time')})")
            
    except Exception as e:
        print(f"API Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug())
