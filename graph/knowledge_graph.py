import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from graph.entity_extractor import EntityExtractor, ExtractedEntity
from graph.identity_resolver import (
    ALIAS_STRENGTH_MEDIUM,
    ALIAS_STRENGTH_STRONG,
    IdentityAlias,
    ResolvedIdentity,
)


class KnowledgeGraph:
    """
    Quản lý Đồ thị Tri thức (Knowledge Graph).
    Chịu trách nhiệm:
    - Lưu trữ và cập nhật các Thực thể (Entities) và Quan hệ (Relationships).
    - Hợp nhất Danh tính (Identity Resolution) cho người dùng/đối tượng.
    - Truy vấn Đồ thị để tìm kiếm các tài liệu và thực thể liên quan (GraphRAG).
    - Cung cấp dữ liệu cho việc hiển thị đồ thị trên UI.
    """
    def __init__(self, session: AsyncSession):
        self._session = session
        self._extractor = EntityExtractor()

    async def upsert_entity(self, entity: ExtractedEntity) -> str:
        existing_id = await self._find_entity_id(
            normalized_name=entity.normalized_name,
            entity_type=entity.entity_type,
        )
        if existing_id:
            await self._session.execute(
                text("""
                    UPDATE entities
                    SET name = :name
                    WHERE id = :id
                """),
                {"id": existing_id, "name": entity.name},
            )
            await self._upsert_aliases(existing_id, [entity.name], entity.entity_type)
            return existing_id

        entity_id = str(uuid.uuid4())
        await self._session.execute(
            text("""
                INSERT INTO entities (id, name, normalized_name, entity_type)
                VALUES (:id, :name, :normalized_name, :entity_type)
            """),
            {
                "id": entity_id,
                "name": entity.name,
                "normalized_name": entity.normalized_name,
                "entity_type": entity.entity_type,
            },
        )
        await self._upsert_aliases(entity_id, [entity.name], entity.entity_type)
        return entity_id

    async def upsert_identity(self, identity: ResolvedIdentity) -> str:
        existing_id = await self._find_identity_entity_id(identity)
        if existing_id:
            await self._update_identity_name(existing_id, identity.canonical_name)
            await self._upsert_aliases(existing_id, identity.aliases, "person")
            return existing_id

        entity_id = str(uuid.uuid4())
        await self._session.execute(
            text("""
                INSERT INTO entities (id, name, normalized_name, entity_type)
                VALUES (:id, :name, :normalized_name, 'person')
            """),
            {
                "id": entity_id,
                "name": identity.canonical_name,
                "normalized_name": identity.normalized_name,
            },
        )
        await self._upsert_aliases(entity_id, identity.aliases, "person")
        return entity_id

    async def link_document_entities(self, document_id: str, entities: list[ExtractedEntity]) -> None:
        await self._session.execute(
            text("DELETE FROM document_entities WHERE document_id = :document_id AND entity_type != 'person'"),
            {"document_id": document_id},
        )

        if not entities:
            try:
                await self._session.commit()
            except Exception:
                await self._session.rollback()
                raise
            return

        # 1. Bulk fetch existing entities (giảm N Select xuống còn 1)
        normalized_names = list({e.normalized_name for e in entities if e.normalized_name})
        existing_entities = {}
        if normalized_names:
            result = await self._session.execute(
                text("""
                    SELECT id::text AS entity_id, normalized_name, entity_type
                    FROM entities
                    WHERE normalized_name = ANY(:names)
                """),
                {"names": normalized_names}
            )
            existing_entities = {(row["normalized_name"], row["entity_type"]): row["entity_id"] for row in result.mappings().all()}

        entities_to_insert = []
        entities_to_update = []
        aliases_to_upsert = []
        seen_aliases = set()
        entity_ids = []

        for entity in entities:
            key = (entity.normalized_name, entity.entity_type)
            if key in existing_entities:
                ent_id = existing_entities[key]
                entities_to_update.append({"id": ent_id, "name": entity.name})
            else:
                ent_id = str(uuid.uuid4())
                existing_entities[key] = ent_id
                entities_to_insert.append({
                    "id": ent_id,
                    "name": entity.name,
                    "normalized_name": entity.normalized_name,
                    "entity_type": entity.entity_type
                })
            
            entity_ids.append(ent_id)

            # Chuẩn bị Upsert Alias (thay thế cho việc gọi hàm con nhiều lần)
            alias_val = entity.name
            normalized_alias = self._extractor.normalize(alias_val)
            if normalized_alias:
                alias_key = (ent_id, normalized_alias)
                if alias_key not in seen_aliases:
                    seen_aliases.add(alias_key)
                    aliases_to_upsert.append({
                        "entity_id": ent_id,
                        "normalized_alias": normalized_alias,
                        "alias_value": alias_val,
                        "alias_type": entity.entity_type,
                        "alias_strength": 1
                    })

        # 2. Bulk Insert / Update Entities
        if entities_to_update:
            unique_updates = list({u["id"]: u for u in entities_to_update}.values())
            await self._session.execute(
                text("UPDATE entities SET name = :name WHERE id = :id"),
                unique_updates
            )
        if entities_to_insert:
            await self._session.execute(
                text("INSERT INTO entities (id, name, normalized_name, entity_type) VALUES (:id, :name, :normalized_name, :entity_type)"),
                entities_to_insert
            )

        # 3. Bulk Upsert Aliases
        if aliases_to_upsert:
            await self._session.execute(
                text("""
                    INSERT INTO entity_aliases (entity_id, normalized_alias, alias_value, alias_type, alias_strength)
                    VALUES (:entity_id, :normalized_alias, :alias_value, :alias_type, :alias_strength)
                    ON CONFLICT (entity_id, normalized_alias) DO UPDATE SET
                        alias_value = EXCLUDED.alias_value,
                        alias_type = EXCLUDED.alias_type,
                        alias_strength = GREATEST(entity_aliases.alias_strength, EXCLUDED.alias_strength)
                """),
                aliases_to_upsert
            )

        # 4. Bulk Insert Document Entities
        doc_entities_to_insert = []
        seen_doc_entities = set()
        for entity, ent_id in zip(entities, entity_ids):
            de_key = (document_id, ent_id, entity.entity_type)
            if de_key not in seen_doc_entities:
                seen_doc_entities.add(de_key)
                doc_entities_to_insert.append({
                    "document_id": document_id,
                    "entity_id": ent_id,
                    "entity_type": entity.entity_type
                })
        if doc_entities_to_insert:
            await self._session.execute(
                text("INSERT INTO document_entities (document_id, entity_id, entity_type) VALUES (:document_id, :entity_id, :entity_type) ON CONFLICT DO NOTHING"),
                doc_entities_to_insert
            )

        # 5. Bulk Insert Entity Relations (tính toán trọng số trong bộ nhớ trước)
        relation_weights = {}
        for left_id, right_id in zip(entity_ids, entity_ids[1:]):
            r_key = (left_id, right_id)
            relation_weights[r_key] = relation_weights.get(r_key, 0) + 1

        relations_to_upsert = [
            {"id": str(uuid.uuid4()), "source_id": s, "target_id": t, "weight_inc": w}
            for (s, t), w in relation_weights.items()
        ]
        if relations_to_upsert:
            await self._session.execute(
                text("""
                    INSERT INTO entity_relations (id, source_id, target_id, relation_type, weight)
                    VALUES (:id, :source_id, :target_id, 'co_occurs', :weight_inc)
                    ON CONFLICT (source_id, target_id, relation_type) 
                    DO UPDATE SET weight = entity_relations.weight + EXCLUDED.weight
                """),
                relations_to_upsert
            )

        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

    async def link_document_identities(self, document_id: str, identities: list[ResolvedIdentity]) -> None:
        await self._session.execute(
            text("DELETE FROM document_entities WHERE document_id = :document_id AND entity_type = 'person'"),
            {"document_id": document_id},
        )

        for identity in identities:
            entity_id = await self.upsert_identity(identity)
            await self._session.execute(
                text("""
                    INSERT INTO document_entities (document_id, entity_id, entity_type)
                    VALUES (:document_id, :entity_id, 'person')
                    ON CONFLICT DO NOTHING
                """),
                {
                    "document_id": document_id,
                    "entity_id": entity_id,
                },
            )

        try:
            await self._session.commit()
        except Exception:
            await self._session.rollback()
            raise

    async def find_related_documents(
        self,
        entity_names: list[str],
        limit: int = 20,
    ) -> list[str]:
        normalized = self._normalize_candidates(entity_names)
        if not normalized:
            return []

        result = await self._session.execute(
            text("""
                SELECT de.document_id::text
                FROM document_entities de
                JOIN entities e ON e.id = de.entity_id
                LEFT JOIN entity_aliases ea ON ea.entity_id = e.id
                WHERE e.normalized_name = ANY(:normalized_names)
                   OR ea.normalized_alias = ANY(:normalized_names)
                GROUP BY de.document_id
                ORDER BY COUNT(*) DESC
                LIMIT :limit
            """),
            {
                "normalized_names": normalized,
                "limit": limit,
            },
        )
        return list(result.scalars().all())

    async def find_related_entities(self, entity_name: str, min_weight: int = 1, limit: int = 20) -> list[str]:
        normalized_values = self._normalize_candidates([entity_name])
        if not normalized_values:
            return []

        # Find entities where this entity is either source or target
        result = await self._session.execute(
            text("""
                WITH start_nodes AS (
                    SELECT id FROM entities WHERE normalized_name = ANY(:normalized_values)
                    UNION
                    SELECT entity_id FROM entity_aliases WHERE normalized_alias = ANY(:normalized_values)
                ),
                peers AS (
                    SELECT target_id as peer_id, weight FROM entity_relations 
                    WHERE source_id IN (SELECT id FROM start_nodes) AND weight >= :min_weight
                    UNION
                    SELECT source_id as peer_id, weight FROM entity_relations 
                    WHERE target_id IN (SELECT id FROM start_nodes) AND weight >= :min_weight
                )
                SELECT DISTINCT e.name, p.weight
                FROM entities e
                JOIN peers p ON e.id = p.peer_id
                ORDER BY p.weight DESC
                LIMIT :limit
            """),
            {"normalized_values": normalized_values, "min_weight": min_weight, "limit": limit},
        )
        return [row[0] for row in result.all()]

    async def _find_entity_id(self, normalized_name: str, entity_type: str) -> str | None:
        result = await self._session.execute(
            text("""
                SELECT id::text
                FROM entities
                WHERE normalized_name = :normalized_name
                  AND entity_type = :entity_type
                LIMIT 1
            """),
            {
                "normalized_name": normalized_name,
                "entity_type": entity_type,
            },
        )
        return result.scalar()

    async def _find_identity_entity_id(self, identity: ResolvedIdentity) -> str | None:
        alias_values = [alias.normalized_value for alias in identity.aliases]
        if not alias_values:
            alias_values = [identity.normalized_name]

        result = await self._session.execute(
            text("""
                SELECT
                    e.id::text AS entity_id,
                    e.normalized_name,
                    ea.normalized_alias,
                    ea.alias_type,
                    COALESCE(ea.alias_strength, 1) AS alias_strength
                FROM entities e
                LEFT JOIN entity_aliases ea ON ea.entity_id = e.id
                WHERE e.entity_type = 'person'
                  AND (
                        e.normalized_name = :normalized_name
                     OR ea.normalized_alias = ANY(:aliases)
                  )
            """),
            {
                "normalized_name": identity.normalized_name,
                "aliases": alias_values,
            },
        )
        rows = result.mappings().all()
        if not rows:
            return None

        candidates: dict[str, dict[str, int]] = {}
        strong_aliases = {
            alias.normalized_value
            for alias in identity.aliases
            if alias.strength >= ALIAS_STRENGTH_STRONG
        }
        medium_aliases = {
            alias.normalized_value
            for alias in identity.aliases
            if alias.strength >= ALIAS_STRENGTH_MEDIUM
            and alias.alias_type in {"username", "handle", "account_id"}
        }
        allow_name_only_match = not strong_aliases and not medium_aliases

        for row in rows:
            entity_id = row["entity_id"]
            candidate = candidates.setdefault(
                entity_id,
                {
                    "score": 0,
                    "exact_name": 0,
                    "strong_match": 0,
                    "medium_match": 0,
                },
            )
            if row["normalized_name"] == identity.normalized_name and candidate["exact_name"] == 0:
                candidate["score"] += 10
                candidate["exact_name"] = 1
            normalized_alias = row["normalized_alias"]
            if normalized_alias in strong_aliases and candidate["strong_match"] == 0:
                candidate["score"] += 100
                candidate["strong_match"] = 1
            elif normalized_alias in medium_aliases and candidate["medium_match"] == 0:
                candidate["score"] += 40
                candidate["medium_match"] = 1

        ranked = sorted(
            candidates.items(),
            key=lambda item: (
                item[1]["score"],
                item[1]["strong_match"],
                item[1]["medium_match"],
                item[1]["exact_name"],
            ),
            reverse=True,
        )
        if not ranked:
            return None

        best_id, best = ranked[0]
        top_score = best["score"]
        tied = [entity_id for entity_id, data in ranked if data["score"] == top_score]

        if top_score >= 40 and len(tied) == 1:
            return best_id
        if allow_name_only_match and top_score >= 10 and len(tied) == 1 and best["exact_name"] == 1:
            return best_id
        return None

    async def _update_identity_name(self, entity_id: str, incoming_name: str) -> None:
        result = await self._session.execute(
            text("SELECT name FROM entities WHERE id = :id"),
            {"id": entity_id},
        )
        current_name = result.scalar() or ""
        chosen_name = max((current_name, incoming_name), key=self._identity_name_rank)
        await self._session.execute(
            text("""
                UPDATE entities
                SET name = :name
                WHERE id = :id
            """),
            {"id": entity_id, "name": chosen_name},
        )

    async def _upsert_aliases(
        self,
        entity_id: str,
        aliases: list[str | IdentityAlias],
        alias_type: str,
    ) -> None:
        for alias in aliases:
            if isinstance(alias, IdentityAlias):
                normalized_alias = alias.normalized_value
                alias_value = alias.value
                current_type = alias.alias_type
                alias_strength = alias.strength
            else:
                normalized_alias = self._extractor.normalize(alias)
                alias_value = alias
                current_type = alias_type
                alias_strength = 1

            if not normalized_alias:
                continue

            await self._session.execute(
                text("""
                    INSERT INTO entity_aliases (
                        entity_id,
                        normalized_alias,
                        alias_value,
                        alias_type,
                        alias_strength
                    )
                    VALUES (
                        :entity_id,
                        :normalized_alias,
                        :alias_value,
                        :alias_type,
                        :alias_strength
                    )
                    ON CONFLICT (entity_id, normalized_alias)
                    DO UPDATE SET
                        alias_value = EXCLUDED.alias_value,
                        alias_type = EXCLUDED.alias_type,
                        alias_strength = GREATEST(entity_aliases.alias_strength, EXCLUDED.alias_strength)
                """),
                {
                    "entity_id": entity_id,
                    "normalized_alias": normalized_alias,
                    "alias_value": alias_value,
                    "alias_type": current_type,
                    "alias_strength": alias_strength,
                },
            )

    def _normalize_candidates(self, entity_names: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()

        for entity_name in entity_names:
            typed = self._extractor.extract_typed(entity_name)
            if typed:
                candidates = [entity.normalized_name for entity in typed]
            else:
                candidates = [self._extractor.normalize(entity_name)]

            for candidate in candidates:
                if candidate and candidate not in seen:
                    seen.add(candidate)
                    normalized.append(candidate)

        return normalized

    @staticmethod
    def _identity_name_rank(value: str) -> tuple[int, int]:
        stripped = (value or "").strip()
        return (
            1 if "@" not in stripped else 0,
            len(stripped),
        )
