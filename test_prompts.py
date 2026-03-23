import asyncio
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        # First login
        res = await client.post("http://localhost:8000/api/auth/token", data={"username": "admin@mygpt.vn", "password": "password"})
        if not res.is_success:
            print("Login failed:", res.text)
            return
            
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # Test Get List
        r1 = await client.get("http://localhost:8000/api/prompts", headers=headers)
        print("LIST:", r1.status_code, len(r1.json().get('prompts', [])) if r1.is_success else r1.text)
        
        if r1.is_success and len(r1.json().get('prompts', [])) > 0:
            doc_type = r1.json()['prompts'][0]['doc_type']
            print("Found doc_type:", doc_type)
            
            # Test Get One
            r2 = await client.get(f"http://localhost:8000/api/prompts/{doc_type}", headers=headers)
            print("GET ONE:", r2.status_code, r2.json() if r2.is_success else r2.text)
            
            # Test Reset
            r3 = await client.post(f"http://localhost:8000/api/prompts/{doc_type}/reset", headers=headers)
            print("RESET:", r3.status_code, r3.json() if r3.is_success else r3.text)
            
            # Test Put
            r4 = await client.put(f"http://localhost:8000/api/prompts/{doc_type}", headers=headers, json={"system_prompt": "test update 123"})
            print("PUT:", r4.status_code, r4.json() if r4.is_success else r4.text)

if __name__ == "__main__":
    asyncio.run(main())
