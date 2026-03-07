import re


class EntityExtractor:
    CAMEL_CASE = re.compile(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b")
    ACRONYM    = re.compile(r"\b[A-Z]{2,6}\b")
    EMAIL      = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[a-z]{2,}\b")

    def extract(self, text: str) -> list[str]:
        entities = set()
        entities.update(self.CAMEL_CASE.findall(text))
        entities.update(self.ACRONYM.findall(text))
        entities.update(self.EMAIL.findall(text))
        return list(entities)