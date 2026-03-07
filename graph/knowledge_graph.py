from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import uuid


class KnowledgeGraph:
    def __init__(self, session: AsyncSession):
        self._session = session

    async def add_entity(self, name: str, entity_type: str = "UNKNOWN") -> str:
        entity_id = str(uuid.uuid4())
        await self._session.execute(
            text("""
                INSERT INTO entities (id, name, entity_type)
                VALUES (:id, :name, :type)
                ON CONFLICT DO NOTHING
            """),
            {"id": entity_id, "name": name, "type": entity_type},
        )
        await self._session.commit()
        return entity_id

    async def add_relation(self, source_id: str, target_id: str, relation_type: str) -> None:
        await self._session.execute(
            text("""
                INSERT INTO entity_relations (id, source_id, target_id, relation_type)
                VALUES (:id, :source, :target, :rel)
                ON CONFLICT DO NOTHING
            """),
            {"id": str(uuid.uuid4()), "source": source_id, "target": target_id, "rel": relation_type},
        )
        await self._session.commit()

    async def find_related_entities(self, entity_name: str) -> list[str]:
        result = await self._session.execute(
            text("""
                SELECT e2.name FROM entities e1
                JOIN entity_relations er ON er.source_id = e1.id
                JOIN entities e2 ON e2.id = er.target_id
                WHERE e1.name = :name LIMIT 20
            """),
            {"name": entity_name},
        )
        return [r[0] for r in result.all()]