import re
from dataclasses import dataclass, field

from models.document import Document, SourceType


@dataclass(frozen=True)
class ResolvedIdentity:
    canonical_name: str
    normalized_name: str
    aliases: list[str] = field(default_factory=list)


class IdentityResolver:
    SLACK_SENDER = re.compile(r"^\[\d{2}:\d{2}\]\s+(.+?):", re.MULTILINE)
    SLACK_NAMED_USER = re.compile(r"^(?P<display>.+?)\s+\((?P<username>[^()]+)\)$")
    EMAIL = re.compile(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,})\b", re.IGNORECASE)

    IGNORED_NAMES = {"unknown", "slack", "file_server", "confluence", "jira"}

    def resolve(self, doc: Document) -> list[ResolvedIdentity]:
        identities: dict[str, ResolvedIdentity] = {}

        self._add_identity(identities, self._from_author(doc.author))

        if doc.source == SourceType.SLACK:
            for sender in self.SLACK_SENDER.findall(doc.content):
                self._add_identity(identities, self._from_slack_sender(sender))

        if doc.source == SourceType.JIRA:
            self._add_identity(identities, self._from_named_identity(
                doc.metadata.get("creator_name"),
                email=doc.metadata.get("creator_email"),
                username=doc.metadata.get("creator_account"),
            ))
            self._add_identity(identities, self._from_named_identity(
                doc.metadata.get("assignee_name"),
                email=doc.metadata.get("assignee_email"),
                username=doc.metadata.get("assignee_account"),
            ))

        if doc.source == SourceType.CONFLUENCE:
            self._add_identity(identities, self._from_named_identity(
                doc.metadata.get("author_name"),
                email=doc.metadata.get("author_email"),
                username=doc.metadata.get("author_username"),
            ))

        for email in self.EMAIL.findall(doc.content):
            self._add_identity(identities, self._from_email(email))

        return sorted(identities.values(), key=lambda item: item.normalized_name)

    def _from_author(self, author: str | None) -> ResolvedIdentity | None:
        return self._from_named_identity(author)

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
        normalized_email = email.strip().lower()
        localpart = normalized_email.split("@", 1)[0]
        canonical_name = f"@{localpart}"
        aliases = [normalized_email, localpart, f"@{localpart}"]
        return self._build_identity(canonical_name, aliases)

    def _from_named_identity(
        self,
        name: str | None,
        email: str | None = None,
        username: str | None = None,
    ) -> ResolvedIdentity | None:
        if not name:
            return None

        name = re.sub(r"\s+", " ", name).strip()
        if not name or name.lower() in self.IGNORED_NAMES:
            return None

        aliases = [name]
        if username:
            user = username.strip().lstrip("@")
            if user:
                aliases.extend([user, f"@{user}"])
        if email:
            normalized_email = email.strip().lower()
            localpart = normalized_email.split("@", 1)[0]
            aliases.extend([normalized_email, localpart, f"@{localpart}"])

        return self._build_identity(name, aliases)

    def _build_identity(self, canonical_name: str, aliases: list[str]) -> ResolvedIdentity | None:
        cleaned_aliases = []
        seen: set[str] = set()
        for alias in aliases:
            normalized = self._normalize(alias)
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            cleaned_aliases.append(alias.strip())

        if not cleaned_aliases:
            return None

        normalized_name = self._normalize(canonical_name)
        if not normalized_name:
            return None

        return ResolvedIdentity(
            canonical_name=canonical_name.strip(),
            normalized_name=normalized_name,
            aliases=cleaned_aliases,
        )

    def _add_identity(
        self,
        identities: dict[str, ResolvedIdentity],
        identity: ResolvedIdentity | None,
    ) -> None:
        if identity is None:
            return

        existing = identities.get(identity.normalized_name)
        if existing is None:
            identities[identity.normalized_name] = identity
            return

        merged_aliases = existing.aliases + [alias for alias in identity.aliases if alias not in existing.aliases]
        identities[identity.normalized_name] = ResolvedIdentity(
            canonical_name=existing.canonical_name,
            normalized_name=existing.normalized_name,
            aliases=merged_aliases,
        )

    @staticmethod
    def _normalize(value: str) -> str:
        value = value.strip().strip(".,:;()[]{}<>\"'")
        value = value.lstrip("@")
        value = re.sub(r"\s+", " ", value)
        return value.lower()
