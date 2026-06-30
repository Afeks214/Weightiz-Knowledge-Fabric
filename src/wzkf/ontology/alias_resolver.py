from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class ConceptReviewStatus(StrEnum):
    RESOLVED = "RESOLVED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass(frozen=True)
class ConceptResolution:
    canonical_name: str
    status: ConceptReviewStatus
    confidence: float
    matched_alias: str | None = None


class AliasResolver:
    def __init__(self, aliases: dict[str, str]):
        self.aliases = {_normalize(alias): canonical for alias, canonical in aliases.items()}

    @classmethod
    def with_default_seed(cls) -> "AliasResolver":
        aliases = {
            "Limit Order Book": "Limit Order Book",
            "LOB": "Limit Order Book",
            "order book": "Limit Order Book",
            "Order Book": "Limit Order Book",
            "Market Depth": "Limit Order Book",
            "order book dynamics": "Limit Order Book",
            "expect tests": "Expect Tests",
            "expect-test": "Expect Tests",
            "ppx_expect": "Expect Tests",
        }
        return cls(aliases)

    def resolve(self, candidate: str) -> ConceptResolution:
        key = _normalize(candidate)
        if key in self.aliases:
            return ConceptResolution(
                canonical_name=self.aliases[key],
                status=ConceptReviewStatus.RESOLVED,
                confidence=1.0,
                matched_alias=candidate,
            )
        if "order book" in key:
            return ConceptResolution(
                canonical_name="Limit Order Book",
                status=ConceptReviewStatus.RESOLVED,
                confidence=0.86,
                matched_alias=candidate,
            )
        return ConceptResolution(
            canonical_name=candidate.strip(),
            status=ConceptReviewStatus.REVIEW_REQUIRED,
            confidence=0.5,
            matched_alias=None,
        )


def _normalize(value: str) -> str:
    lowered = value.casefold().replace("_", " ")
    cleaned = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(cleaned.split())
