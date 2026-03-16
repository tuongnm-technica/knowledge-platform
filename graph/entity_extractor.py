import re
from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedEntity:
    name: str
    entity_type: str
    normalized_name: str


class EntityExtractor:
    JIRA_KEY = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")
    EMAIL = re.compile(r"\b([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,})\b", re.IGNORECASE)
    SLACK_USER = re.compile(r"(?<!\w)@([A-Za-z0-9._-]{2,})\b")
    SLACK_CHANNEL = re.compile(r"(?<!\w)#([A-Za-z0-9_-]{2,})\b")
    CAMEL_CASE = re.compile(r"\b([A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+)\b")
    SERVICE_TOKEN = re.compile(r"\b([A-Za-z][A-Za-z0-9._-]*(?:service|api|worker|gateway|client|server|job|consumer|producer))\b", re.IGNORECASE)
    ACRONYM = re.compile(r"\b([A-Z][A-Z0-9]{1,9})\b")

    PROJECT_STOPWORDS = {
        "API", "HTTP", "HTTPS", "JWT", "JSON", "SQL", "TCP", "UDP", "URL",
        "HTML", "CSS", "UI", "UX", "CPU", "GPU", "RAM", "SDK", "CLI",
        "REST", "RPC", "ETL", "PDF", "CSV", "XML", "QDRANT", "OLLAMA",
    }

    PERSON_STOPWORDS = {"channel", "here", "everyone"}

    def extract(self, text: str) -> list[str]:
        return [entity.name for entity in self.extract_typed(text)]

    def extract_typed(self, text: str) -> list[ExtractedEntity]:
        entities: dict[tuple[str, str], ExtractedEntity] = {}
        if not text:
            return []

        for match in self.JIRA_KEY.findall(text):
            self._add(entities, match, "jira_issue")
        for match in self.EMAIL.findall(text):
            self._add(entities, match, "email")
        for match in self.SLACK_USER.findall(text):
            self._add(entities, match, "person")
        for match in self.SLACK_CHANNEL.findall(text):
            self._add(entities, match, "channel")
        for match in self.SERVICE_TOKEN.findall(text):
            self._add(entities, match, "service")
        for match in self.CAMEL_CASE.findall(text):
            self._add(entities, match, "service")
        for match in self.ACRONYM.findall(text):
            self._add(entities, match, "project")

        return sorted(entities.values(), key=lambda item: (item.entity_type, item.normalized_name))

    def _add(self, entities: dict[tuple[str, str], ExtractedEntity], raw_name: str, entity_type: str) -> None:
        cleaned = raw_name.strip().strip(".,:;()[]{}<>\"'")
        if not cleaned:
            return

        canonical_name = self.to_canonical_name(cleaned, entity_type)
        normalized_name = self.normalize(cleaned, entity_type=entity_type)

        if not normalized_name or len(normalized_name) < 2:
            return
        if entity_type == "project" and canonical_name in self.PROJECT_STOPWORDS:
            return
        if entity_type == "person" and normalized_name in self.PERSON_STOPWORDS:
            return

        key = (normalized_name, entity_type)
        entities[key] = ExtractedEntity(
            name=canonical_name,
            entity_type=entity_type,
            normalized_name=normalized_name,
        )

    def to_canonical_name(self, value: str, entity_type: str) -> str:
        value = value.strip()
        if entity_type == "jira_issue":
            return value.upper()
        if entity_type == "email":
            return value.lower()
        if entity_type == "person":
            handle = value.lstrip("@")
            return f"@{handle.lower()}" if handle.upper().startswith("U") else f"@{handle}"
        if entity_type == "channel":
            return f"#{value.lstrip('#').lower()}"
        if entity_type == "service":
            value = self._split_compound_tokens(value)
            value = re.sub(r"[_\-.]+", " ", value)
            return re.sub(r"\s+", " ", value).strip()
        if entity_type == "project":
            return value.upper()
        return value

    def normalize(self, value: str, entity_type: str | None = None) -> str:
        value = value.strip().strip(".,:;()[]{}<>\"'")
        if not value:
            return ""

        if entity_type == "jira_issue":
            return value.upper()
        if entity_type == "email":
            return value.lower()
        if entity_type == "person":
            return value.lstrip("@").lower()
        if entity_type == "channel":
            return value.lstrip("#").lower()
        if entity_type == "service":
            value = self._split_compound_tokens(value)
            value = re.sub(r"[_\-.]+", " ", value)
            return re.sub(r"\s+", " ", value).strip().lower()
        if entity_type == "project":
            return value.upper()

        value = re.sub(r"\s+", " ", value)
        return value.lower()

    @staticmethod
    def _split_compound_tokens(value: str) -> str:
        value = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
        value = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1 \2", value)
        return value
