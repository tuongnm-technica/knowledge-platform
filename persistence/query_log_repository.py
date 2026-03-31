import uuid
from datetime import datetime
from sqlalchemy import text, insert
from sqlalchemy.ext.asyncio import AsyncSession
from storage.db.db import QueryLogORM

class QueryLogRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def log_query(self, 
                        user_id: str, 
                        query: str, 
                        rewritten_query: str = None, 
                        answer: str = None, 
                        sources_used: list = None, 
                        edges_used: list = None,
                        result_count: int = 0) -> str:
        """
        Lưu log truy vấn cùng với ngữ cảnh (Sources/Edges) để phục vụ Reinforcement Learning.
        """
        query_id = str(uuid.uuid4())
        
        # Clean edges list (ensure unique UUID strings)
        edges = list(set([str(e) for e in (edges_used or []) if e]))
        
        stmt = insert(QueryLogORM).values(
            id=query_id,
            user_id=user_id,
            query=query,
            rewritten_query=rewritten_query,
            answer=answer,
            sources_used=sources_used or [],
            edges_used=edges,
            result_count=result_count,
            feedback=0,
            created_at=datetime.utcnow()
        )
        
        await self._session.execute(stmt)
        await self._session.commit()
        return query_id

    async def submit_feedback(self, query_id: str, feedback: int) -> dict:
        """
        Cập nhật feedback từ người dùng (👍: 1, 👎: -1).
        Trả về metadata của query để kích hoạt Reinforcement Engine.
        """
        result = await self._session.execute(
            text("UPDATE query_logs SET feedback = :f, feedback_at = :now WHERE id = :id RETURNING edges_used, sources_used"),
            {"f": feedback, "id": query_id, "now": datetime.utcnow()}
        )
        row = result.fetchone()
        if row:
            await self._session.commit()
            return {
                "edges": row[0] or [],
                "sources": row[1] or []
            }
        return None
