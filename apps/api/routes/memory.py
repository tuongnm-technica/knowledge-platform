from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from storage.db.db import get_db
from persistence.project_memory_repository import ProjectMemoryRepository

router = APIRouter(prefix="/memory", tags=["memory"])

@router.get("")
async def list_memories(db: AsyncSession = Depends(get_db)):
    repo = ProjectMemoryRepository(db)
    grouped = await repo.get_all_grouped()
    
    # Flatten/Format for frontend
    # web/memory.ts expects MemoryItem { type, key, value }
    items = []
    for mtype, records in grouped.items():
        for r in records:
            items.append({
                "type": r["memory_type"],
                "key": r["key"],
                "value": r["content"]
            })
    return items
