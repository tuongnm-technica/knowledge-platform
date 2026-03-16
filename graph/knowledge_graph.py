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

        entity_ids: list[str] = []
        for entity in entities:
            entity_id = await self.upsert_entity(entity)
            entity_ids.append(entity_id)
            await self._session.execute(
                text("""
                    INSERT INTO document_entities (document_id, entity_id, entity_type)
                    VALUES (:document_id, :entity_id, :entity_type)
                    ON CONFLICT DO NOTHING
                """),
                {
                    "document_id": document_id,
                    "entity_id": entity_id,
                    "entity_type": entity.entity_type,
                },
            )

        for left, right in zip(entity_ids, entity_ids[1:]):
            await self._session.execute(
                text("""
                    INSERT INTO entity_relations (id, source_id, target_id, relation_type)
                    VALUES (:id, :source_id, :target_id, 'co_occurs')
                    ON CONFLICT DO NOTHING
                """),
                {
                    "id": str(uuid.uuid4()),
                    "source_id": left,
                    "target_id": right,
                },
            )

        await self._session.commit()

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

        await self._session.commit()

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

    async def find_related_entities(self, entity_name: str) -> list[str]:
        normalized_values = self._normalize_candidates([entity_name])
        if not normalized_values:
            return []

        result = await self._session.execute(
            text("""
                SELECT e2.name
                FROM entities e1
                LEFT JOIN entity_aliases ea1 ON ea1.entity_id = e1.id
                JOIN entity_relations er ON er.source_id = e1.id
                JOIN entities e2 ON e2.id = er.target_id
                WHERE e1.normalized_name = ANY(:normalized_values)
                   OR ea1.normalized_alias = ANY(:normalized_values)
                LIMIT 20
            """),
            {"normalized_values": normalized_values},
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
