import re
from dataclasses import dataclass
from typing import Literal

#third-party imports
from pydantic import BaseModel, Field, ValidationError

#project imports
from memory_service.config import get_settings
from memory_service.schemas.turns import TurnMessage

MemoryCandidateType = Literal["fact", "preference", "opinion", "event"]


@dataclass(frozen=True)
class MemoryCandidate:
    type: MemoryCandidateType
    key: str
    value: str
    confidence: float
    evidence_quote: str


class ExtractedMemory(BaseModel):
    type: MemoryCandidateType
    key: str = Field(min_length=1)
    value: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_quote: str = Field(min_length=1)


class ExtractedMemories(BaseModel):
    memories: list[ExtractedMemory]


MEMORY_EXTRACTION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "memories": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["fact", "preference", "opinion", "event"],
                    },
                    "key": {"type": "string"},
                    "value": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "evidence_quote": {"type": "string"},
                },
                "required": ["type", "key", "value", "confidence", "evidence_quote"],
            },
        }
    },
    "required": ["memories"],
}


class CombinedMemoryExtractor:
    def __init__(
        self,
        rule_based_extractor: "RuleBasedMemoryExtractor | None" = None,
        llm_extractor: "LLMMemoryExtractor | None" = None,
    ) -> None:
        self.rule_based_extractor = rule_based_extractor or RuleBasedMemoryExtractor()
        self.llm_extractor = llm_extractor or LLMMemoryExtractor()

    async def extract(self, messages: list[TurnMessage]) -> list[MemoryCandidate]:
        candidates = self.rule_based_extractor.extract(messages)
        candidates.extend(await self.llm_extractor.extract(messages))
        return dedupe_candidates(candidates)


class LLMMemoryExtractor:
    def __init__(self, client=None, model: str | None = None, api_key: str | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.openai_extract_model
        self.api_key = api_key if api_key is not None else settings.openai_api_key
        self.client = client

    async def extract(self, messages: list[TurnMessage]) -> list[MemoryCandidate]:
        if not self.api_key and self.client is None:
            return []

        client = self.client or self._build_client()
        try:
            response = await client.responses.create(
                model=self.model,
                input=[
                    {"role": "system", "content": self._system_prompt()},
                    {"role": "user", "content": self._format_messages(messages)},
                ],
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "memory_extraction",
                        "strict": True,
                        "schema": MEMORY_EXTRACTION_SCHEMA,
                    }
                },
                max_output_tokens=1200,
            )
        except Exception:
            return []

        try:
            payload = ExtractedMemories.model_validate_json(response.output_text)
        except (AttributeError, ValidationError, ValueError):
            return []

        return [
            MemoryCandidate(
                type=memory.type,
                key=memory.key,
                value=memory.value,
                confidence=memory.confidence,
                evidence_quote=memory.evidence_quote,
            )
            for memory in payload.memories
        ]

    def _build_client(self):
        from openai import AsyncOpenAI

        return AsyncOpenAI(api_key=self.api_key)

    def _format_messages(self, messages: list[TurnMessage]) -> str:
        return "\n".join(f"{message.role.title()}: {message.content}" for message in messages)

    def _system_prompt(self) -> str:
        return (
            "Extract durable long-term memory facts from the conversation. "
            "Return only facts that are useful for future agent turns. "
            "Use normalized keys like employment.current_company, location.current_city, "
            "location.previous_city, pet.dog.name, preference.communication_style, "
            "preference.diet, opinion.<topic>, or event.<short_topic>. "
            "Do not include raw chat summaries. Use the exact source quote as evidence_quote."
        )


class RuleBasedMemoryExtractor:
    def extract(self, messages: list[TurnMessage]) -> list[MemoryCandidate]:
        text = "\n".join(message.content for message in messages)
        candidates: list[MemoryCandidate] = []

        candidates.extend(self._extract_locations(text))
        candidates.extend(self._extract_employment(text))
        candidates.extend(self._extract_pets(text))
        candidates.extend(self._extract_preferences(text))

        return dedupe_candidates(candidates)

    def _extract_locations(self, text: str) -> list[MemoryCandidate]:
        candidates: list[MemoryCandidate] = []

        for match in re.finditer(
            r"\b(?:just\s+)?moved\s+to\s+(?P<current>[A-Z][A-Za-z .'-]+?)\s+from\s+"
            r"(?P<previous>[A-Z][A-Za-z .'-]+?)(?:[.,;!?]|\s+(?:last|this|and|but)\b|$)",
            text,
            flags=re.IGNORECASE,
        ):
            current = self._clean_value(match.group("current"))
            previous = self._clean_value(match.group("previous"))
            quote = self._clean_quote(match.group(0))
            candidates.append(
                MemoryCandidate(
                    type="fact",
                    key="location.current_city",
                    value=current,
                    confidence=0.92,
                    evidence_quote=quote,
                )
            )
            candidates.append(
                MemoryCandidate(
                    type="fact",
                    key="location.previous_city",
                    value=previous,
                    confidence=0.88,
                    evidence_quote=quote,
                )
            )

        return candidates

    def _extract_employment(self, text: str) -> list[MemoryCandidate]:
        candidates: list[MemoryCandidate] = []
        patterns = [
            r"\bI\s+(?:currently\s+)?work\s+at\s+(?P<company>[A-Z][A-Za-z0-9 &'._-]+?)"
            r"(?:[.,;!?]|\s+(?:last|this|recently|now|and|but)\b|$)",
            r"\bI\s+(?:just\s+)?(?:joined|started\s+at|started\s+working\s+at)\s+"
            r"(?P<company>[A-Z][A-Za-z0-9 &'._-]+?)"
            r"(?:[.,;!?]|\s+(?:last|this|recently|now|and|but)\b|$)",
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                candidates.append(
                    MemoryCandidate(
                        type="fact",
                        key="employment.current_company",
                        value=self._clean_value(match.group("company")),
                        confidence=0.9,
                        evidence_quote=self._clean_quote(match.group(0)),
                    )
                )

        return candidates

    def _extract_pets(self, text: str) -> list[MemoryCandidate]:
        candidates: list[MemoryCandidate] = []
        patterns = [
            r"\bmy\s+(?P<animal>dog|cat)\s+(?:named\s+)?(?P<name>[A-Z][A-Za-z'-]+)",
            r"\b(?P<animal>dog|cat)\s+named\s+(?P<name>[A-Z][A-Za-z'-]+)",
        ]

        for pattern in patterns:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                animal = match.group("animal").lower()
                candidates.append(
                    MemoryCandidate(
                        type="fact",
                        key=f"pet.{animal}.name",
                        value=self._clean_value(match.group("name")),
                        confidence=0.86,
                        evidence_quote=self._clean_quote(match.group(0)),
                    )
                )

        return candidates

    def _extract_preferences(self, text: str) -> list[MemoryCandidate]:
        candidates: list[MemoryCandidate] = []

        if re.search(r"\bI(?:'m| am)\s+vegetarian\b", text, flags=re.IGNORECASE):
            candidates.append(
                MemoryCandidate(
                    type="preference",
                    key="preference.diet",
                    value="vegetarian",
                    confidence=0.9,
                    evidence_quote=self._first_matching_quote(
                        text,
                        r"\bI(?:'m| am)\s+vegetarian\b",
                    ),
                )
            )

        concise_match = re.search(
            r"\bI\s+prefer\s+(?:concise|short|brief)(?:,\s*)?(?:and\s+)?"
            r"(?:direct\s+)?(?:answers|responses|replies)?\b",
            text,
            flags=re.IGNORECASE,
        )
        if concise_match:
            candidates.append(
                MemoryCandidate(
                    type="preference",
                    key="preference.communication_style",
                    value="concise/direct",
                    confidence=0.84,
                    evidence_quote=self._clean_quote(concise_match.group(0)),
                )
            )

        return candidates

    def _first_matching_quote(self, text: str, pattern: str) -> str:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            return ""
        return self._clean_quote(match.group(0))

    def _clean_value(self, value: str) -> str:
        cleaned = re.sub(r"\s+", " ", value).strip(" .,;:!?")
        stop_words = (" last month", " this month", " recently", " now")
        lowered = cleaned.lower()
        for stop_word in stop_words:
            if lowered.endswith(stop_word):
                cleaned = cleaned[: -len(stop_word)].strip()
                break
        return cleaned

    def _clean_quote(self, quote: str) -> str:
        return re.sub(r"\s+", " ", quote).strip()


def dedupe_candidates(candidates: list[MemoryCandidate]) -> list[MemoryCandidate]:
    seen: set[tuple[str, str]] = set()
    unique: list[MemoryCandidate] = []
    for candidate in candidates:
        fingerprint = (candidate.key, candidate.value.lower())
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(candidate)
    return unique
