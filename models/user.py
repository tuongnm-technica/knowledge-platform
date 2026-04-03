from dataclasses import dataclass, field


@dataclass
class User:
    id: str
    email: str
    display_name: str
    groups: list[str] = field(default_factory=list)
    language: str = "vi"

    def can_access(self, document_permissions: list[str]) -> bool:
        return bool(set(self.groups) & set(document_permissions))