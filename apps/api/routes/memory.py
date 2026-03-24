from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from storage.db.db import get_db
from persistence.project_memory_repository import ProjectMemoryRepository
from apps.api.auth.dependencies import CurrentUser, get_current_user

router = APIRouter(prefix="/memory", tags=["memory"])

@router.get("")
async def list_memories(db: AsyncSession = Depends(get_db), _: CurrentUser = Depends(get_current_user)):
    repo = ProjectMemoryRepository(db)
    grouped = await repo.get_all_grouped()
    
    # Format for frontend
    # web/memory.ts expects { memory: Record<string, any[]> }
    formatted_grouped = {}
    for mtype, records in grouped.items():
        formatted_grouped[mtype] = [{
            "type": r["memory_type"],
            "key": r["key"],
            "value": r["content"]
        } for r in records]
    return {"memory": formatted_grouped}
