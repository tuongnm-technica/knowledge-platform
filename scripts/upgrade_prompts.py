import asyncio
import os
import sys

# Add project root to sys.path
sys.path.append(os.getcwd())

from storage.db.db import AsyncSessionLocal
from persistence.skill_prompt_repository import SkillPromptRepository

async def run_upgrade():
    print("🚀 Đang nâng cấp Skill Prompts lên Full Hybrid Edition (20KB+ deep prompts)...")
    try:
        async with AsyncSessionLocal() as session:
            repo = SkillPromptRepository(session)
            count = await repo.seed_defaults()
            print(f"✅ Thành công! Đã nâng cấp {count} prompts từ filesystem vào database.")
    except Exception as e:
        print(f"❌ Lỗi khi nâng cấp: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_upgrade())
