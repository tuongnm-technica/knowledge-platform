import httpx
import asyncio

async def trigger_sync():
    instance_id = "df94a2d8-ff0a-42ae-b2a8-cbd3452ab9c7"
    url = f"http://localhost:8000/api/connectors/{instance_id}/sync"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json={"incremental": False})
            print(f"Status: {resp.status_code}")
            print(f"Response: {resp.json()}")
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(trigger_sync())
