import re
from models.document import Document


class MetadataExtractor:
    def extract(self, doc: Document) -> dict:
        meta = dict(doc.metadata)
        meta["word_count"] = len(doc.content.split())
        meta["char_count"] = len(doc.content)
        meta["extracted_urls"] = self._extract_urls(doc.content)
        meta["language"] = self._detect_language(doc.content)
        return meta

    def _extract_urls(self, text: str) -> list[str]:
        return re.findall(r"https?://[^\s\]>\"']+", text)[:10]

    def _detect_language(self, text: str) -> str:
        viet = len(re.findall(r"[àáảãạăắặẳẵâấậẩẫđèéẻẽẹêếệểễìíỉĩịòóỏõọôốộổỗơớợởỡùúủũụưứựửữỳýỷỹỵ]", text, re.IGNORECASE))
        return "vi" if viet > 5 else "en"