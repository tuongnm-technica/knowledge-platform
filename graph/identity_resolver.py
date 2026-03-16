import re
from dataclasses import dataclass, field

from models.document import Document, SourceType


ALIAS_STRENGTH_WEAK = 1
ALIAS_STRENGTH_MEDIUM = 2
ALIAS_STRENGTH_STRONG = 3


@dataclass(frozen=True)
class IdentityAlias:
    value: str
    normalized_value: str
    alias_type: str
    strength: int


@dataclass(frozen=True)
class ResolvedIdentity:
    canonical_name: str
    normalized_name: str
    aliases: list[IdentityAlias] = field(default_factory=list)


class IdentityResolver:
    SLACK_SENDER = re.compile(r"^\[\d{2}:\d{2}\]\s+(.+?):", re.MULTILINE)
    SLACK_NAMED_USER = re.compile(r"^(?P<display>.+?)\s+\((?P<username>[^()]+)\)$")
    EMAIL = re.compile(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,})\b", re.IGNORECASE)

    IGNORED_NAMES = {"unknown", "slack", "file_server", "confluence", "jira"}

    def resolve(self, doc: Document) -> list[ResolvedIdentity]:
        identities: list[ResolvedIdentity] = []

        self._add_identity(identities, self._from_author(doc.author))

        if doc.source == SourceType.SLACK:
            for sender in self.SLACK_SENDER.findall(doc.content):
                self._add_identity(identities, self._from_slack_sender(sender))
            for participant in doc.metadata.get("participants", []):
                self._add_identity(identities, self._from_participant(participant))

        if doc.source == SourceType.JIRA:
            self._add_identity(
                identities,
                self._from_named_identity(
                    doc.metadata.get("creator_name"),
                    email=doc.metadata.get("creator_email"),
                    username=doc.metadata.get("creator_account"),
                    account_id=doc.metadata.get("creator_account"),
                ),
            )
            self._add_identity(
                identities,
                self._from_named_identity(
                    doc.metadata.get("assignee_name"),
                    email=doc.metadata.get("assignee_email"),
                    username=doc.metadata.get("assignee_account"),
                    account_id=doc.metadata.get("assignee_account"),
                ),
            )

        if doc.source == SourceType.CONFLUENCE:
            self._add_identity(
                identities,
                self._from_named_identity(
                    doc.metadata.get("author_name"),
                    email=doc.metadata.get("author_email"),
                    username=doc.metadata.get("author_username"),
                ),
            )

        for email in self.EMAIL.findall(doc.content):
            self._add_identity(identities, self._from_email(email))

        return sorted(identities, key=lambda item: item.normalized_name)

    def _from_author(self, author: str | None) -> ResolvedIdentity | None:
        return self._from_named_identity(author)

    def _from_participant(self, participant: dict) -> ResolvedIdentity | None:
        return self._from_named_identity(
            participant.get("display_name") or participant.get("real_name") or participant.get("name"),
            email=participant.get("email"),
            username=participant.get("name"),
            account_id=participant.get("user_id"),
        )

    def _from_slack_sender(self, sender: str) -> ResolvedIdentity | None:
        sender = sender.strip()
        match = self.SLACK_NAMED_USER.match(sender)
        if match:
            return self._from_named_identity(
                match.group("display"),
                username=match.group("username"),
            )
        return self._from_named_identity(sender)

    def _from_email(self, email: str | None) -> ResolvedIdentity | None:
        if not email:
            return None

        normalized_email = self._normalize_email(email)
        localpart = normalized_email.split("@", 1)[0]
        aliases = [
            self._alias(normalized_email, "email", ALIAS_STRENGTH_STRONG),
            self._alias(localpart, "username", ALIAS_STRENGTH_MEDIUM),
            self._alias(f"@{localpart}", "handle", ALIAS_STRENGTH_MEDIUM),
        ]
        return self._build_identity(f"@{localpart}", aliases)

    def _from_named_identity(
        self,
        name: str | None,
        email: str | None = None,
        username: str | None = None,
        account_id: str | None = None,
    ) -> ResolvedIdentity | None:
        if not name:
            return None

        name = re.sub(r"\s+", " ", name).strip()
        if not name or name.lower() in self.IGNORED_NAMES:
            return None

        aliases = [
            self._alias(name, "canonical_name", ALIAS_STRENGTH_MEDIUM if " " in name else ALIAS_STRENGTH_WEAK),
            self._alias(name, "display_name", ALIAS_STRENGTH_WEAK),
        ]

        if username:
            user = username.strip().lstrip("@")
            if user and re.fullmatch(r"[A-Za-z0-9._-]{2,100}", user):
                aliases.extend(
                    [
                        self._alias(user, "username", ALIAS_STRENGTH_MEDIUM),
                        self._alias(f"@{user}", "handle", ALIAS_STRENGTH_MEDIUM),
                    ]
                )

        if account_id:
            aliases.append(self._alias(account_id, "account_id", ALIAS_STRENGTH_MEDIUM))

        if email:
            normalized_email = self._normalize_email(email)
            localpart = normalized_email.split("@", 1)[0]
            aliases.extend(
                [
                    self._alias(normalized_email, "email", ALIAS_STRENGTH_STRONG),
                    self._alias(localpart, "username", ALIAS_STRENGTH_MEDIUM),
                    self._alias(f"@{localpart}", "handle", ALIAS_STRENGTH_MEDIUM),
                ]
            )

        return self._build_identity(name, aliases)

    def _build_identity(self, canonical_name: str, aliases: list[IdentityAlias | None]) -> ResolvedIdentity | None:
        normalized_name = self._normalize_name(canonical_name)
        if not normalized_name:
            return None

        alias_map: dict[tuple[str, str], IdentityAlias] = {}
        canonical_alias = self._alias(canonical_name, "canonical_name", ALIAS_STRENGTH_MEDIUM)
        if canonical_alias:
            alias_map[(canonical_alias.alias_type, canonical_alias.normalized_value)] = canonical_alias

        for alias in aliases:
            if alias is None:
                continue
            key = (alias.alias_type, alias.normalized_value)
            existing = alias_map.get(key)
            if existing is None or alias.strength > existing.strength:
                alias_map[key] = alias

        if not alias_map:
            return None

        cleaned_aliases = sorted(
            alias_map.values(),
            key=lambda item: (-item.strength, item.alias_type, item.normalized_value),
        )
        return ResolvedIdentity(
            canonical_name=canonical_name.strip(),
            normalized_name=normalized_name,
            aliases=cleaned_aliases,
        )

    def _add_identity(
        self,
        identities: list[ResolvedIdentity],
        identity: ResolvedIdentity | None,
    ) -> None:
        if identity is None:
            return

        for index, existing in enumerate(identities):
            if self._should_merge(existing, identity):
                identities[index] = self._merge(existing, identity)
                return

        identities.append(identity)

    def _should_merge(self, left: ResolvedIdentity, right: ResolvedIdentity) -> bool:
        if left.normalized_name == right.normalized_name:
            return True

        left_strong = self._strong_aliases(left)
        right_strong = self._strong_aliases(right)
        if left_strong and right_strong and left_strong.intersection(right_strong):
            return True

        left_medium = self._medium_aliases(left)
        right_medium = self._medium_aliases(right)
        if left_medium and right_medium and left_medium.intersection(right_medium):
            return True

        return False

    def _merge(self, left: ResolvedIdentity, right: ResolvedIdentity) -> ResolvedIdentity:
        alias_map: dict[tuple[str, str], IdentityAlias] = {}
        for alias in left.aliases + right.aliases:
            key = (alias.alias_type, alias.normalized_value)
            existing = alias_map.get(key)
            if existing is None or alias.strength > existing.strength:
                alias_map[key] = alias

        preferred_name = self._pick_canonical_name(left.canonical_name, right.canonical_name)
        normalized_name = self._normalize_name(preferred_name) or left.normalized_name
        aliases = sorted(
            alias_map.values(),
            key=lambda item: (-item.strength, item.alias_type, item.normalized_value),
        )
        return ResolvedIdentity(
            canonical_name=preferred_name,
            normalized_name=normalized_name,
            aliases=aliases,
        )

    def _pick_canonical_name(self, left: str, right: str) -> str:
        return max((left.strip(), right.strip()), key=self._canonical_name_rank)

    def _canonical_name_rank(self, value: str) -> tuple[int, int]:
        stripped = value.strip()
        return (
            1 if "@" not in stripped else 0,
            len(stripped),
        )

    def _alias(self, value: str | None, alias_type: str, strength: int) -> IdentityAlias | None:
        if not value:
            return None

        normalized = self._normalize_alias(value, alias_type)
        if not normalized:
            return None

        return IdentityAlias(
            value=value.strip(),
            normalized_value=normalized,
            alias_type=alias_type,
            strength=strength,
        )

    def _strong_aliases(self, identity: ResolvedIdentity) -> set[str]:
        return {
            alias.normalized_value
            for alias in identity.aliases
            if alias.strength >= ALIAS_STRENGTH_STRONG
        }

    def _medium_aliases(self, identity: ResolvedIdentity) -> set[str]:
        return {
            alias.normalized_value
            for alias in identity.aliases
            if alias.strength >= ALIAS_STRENGTH_MEDIUM
            and alias.alias_type in {"username", "handle", "account_id"}
        }

    def _normalize_name(self, value: str) -> str:
        value = value.strip().strip(".,:;()[]{}<>\"'")
        value = re.sub(r"\s+", " ", value)
        return value.lower()

    def _normalize_alias(self, value: str, alias_type: str) -> str:
        value = value.strip().strip(".,:;()[]{}<>\"'")
        if not value:
            return ""

        if alias_type == "email":
            return self._normalize_email(value)
        if alias_type == "handle":
            return value.lstrip("@").lower()
        if alias_type == "channel":
            return value.lstrip("#").lower()
        if alias_type in {"username", "account_id"}:
            return value.lower()
        return re.sub(r"\s+", " ", value).lower()

    @staticmethod
    def _normalize_email(value: str) -> str:
        return value.strip().lower()
