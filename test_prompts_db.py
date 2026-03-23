import asyncio
from storage.db.db import AsyncSessionLocal
from persistence.skill_prompt_repository import SkillPromptRepository

async def main():
    async with AsyncSessionLocal() as session:
        repo = SkillPromptRepository(session)
        prompts = await repo.list_all()
        print("Total prompts:", len(prompts))
        
        if len(prompts) > 0:
            doc_type = prompts[0]['doc_type']
            print("\n--- GET ONE ---")
            p = await repo.get(doc_type)
            print("doc_type:", p['doc_type'])
            print("system_prompt length:", len(p['system_prompt']))
            
            print("\n--- UPDATE ONE ---")
            res = await repo.update_prompt(doc_type=doc_type, system_prompt="test_update", updated_by="admin")
            print("Update result:", res)
            
            p2 = await repo.get(doc_type)
            print("system_prompt after update:", p2['system_prompt'])
            
            print("\n--- RESET ONE ---")
            res2 = await repo.reset_to_default(doc_type=doc_type, updated_by="admin")
            print("Reset result:", res2)
            
            p3 = await repo.get(doc_type)
            print("system_prompt length after reset:", len(p3['system_prompt']))

if __name__ == "__main__":
    asyncio.run(main())
