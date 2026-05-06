#python imports
import re
from dataclasses import dataclass
from typing import Literal

#third-party imports

#project imports
from memory_service.schemas.turns import TurnMessage

MemoryCandidateType = Literal["fact", "preference", "opinion", "event"]


@dataclass(frozen=True)
class MemoryCandidate:
    type: MemoryCandidateType
    key: str
    value: str
    confidence: float
    evidence_quote: str


class RuleBasedMemoryExtractor:
    def extract(self, messages: list[TurnMessage]) -> list[MemoryCandidate]:
        text = "\n".join(message.content for message in messages)
        candidates: list[MemoryCandidate] = []

        candidates.extend(self._extract_locations(text))
        candidates.extend(self._extract_employment(text))
        candidates.extend(self._extract_pets(text))
        candidates.extend(self._extract_preferences(text))

        return self._dedupe(candidates)

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

    def _dedupe(self, candidates: list[MemoryCandidate]) -> list[MemoryCandidate]:
        seen: set[tuple[str, str]] = set()
        unique: list[MemoryCandidate] = []
        for candidate in candidates:
            fingerprint = (candidate.key, candidate.value.lower())
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            unique.append(candidate)
        return unique

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
