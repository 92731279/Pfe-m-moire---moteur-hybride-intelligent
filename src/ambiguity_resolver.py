"""ambiguity_resolver.py — Résolution des ambiguïtés ville/adresse"""

from dataclasses import dataclass
from typing import Optional, List

from src.reference_data import COUNTRY_NAME_TO_CODE, CITIES_BY_COUNTRY
from src.e2_address_parser import parse_address_line


def _norm(value: Optional[str]) -> str:
    if not value:
        return ""
    return " ".join(value.strip().upper().split())


@dataclass
class AmbiguityDecision:
    label: str
    score: int
    reason: str
    confidence: float


def _country_name_to_code(country_name: str) -> Optional[str]:
    return COUNTRY_NAME_TO_CODE.get(_norm(country_name))


def _town_known_for_country(town: str, country_code: str) -> bool:
    known = CITIES_BY_COUNTRY.get(country_code, [])
    town_n = _norm(town)
    return any(_norm(x) == town_n for x in known)


def _score_as_town(line_value: str, country_name: str) -> AmbiguityDecision:
    country_code = _country_name_to_code(country_name)
    line_n = _norm(line_value)
    score = 0
    reasons: List[str] = []

    if country_code:
        score += 2
        reasons.append("country_known")
        if _town_known_for_country(line_n, country_code):
            score += 4
            reasons.append("town_known_for_country")

    if not any(ch.isdigit() for ch in line_value):
        score += 1
        reasons.append("no_digits")

    parsed = parse_address_line(line_value)
    comps = parsed.get("components", {}) or {}
    if "city" in comps:
        score += 2
        reasons.append("libpostal_city")

    confidence = min(0.95, 0.45 + (score * 0.08))
    return AmbiguityDecision(
        label="TOWN", score=score, reason=",".join(reasons), confidence=round(confidence, 2)
    )


def _score_as_address(line_value: str) -> AmbiguityDecision:
    score = 0
    reasons: List[str] = []
    parsed = parse_address_line(line_value)
    comps = parsed.get("components", {}) or {}

    if "road" in comps:
        score += 4
        reasons.append("libpostal_road")
    if "house_number" in comps:
        score += 2
        reasons.append("house_number")
    if "po_box" in comps:
        score += 2
        reasons.append("po_box")
    if any(ch.isdigit() for ch in line_value):
        score += 1
        reasons.append("has_digits")

    confidence = min(0.95, 0.45 + (score * 0.08))
    return AmbiguityDecision(
        label="ADDRESS", score=score, reason=",".join(reasons), confidence=round(confidence, 2)
    )


def resolve_city_country_ambiguity(line_value: str, country_name: str) -> AmbiguityDecision:
    as_town = _score_as_town(line_value, country_name)
    as_address = _score_as_address(line_value)

    if as_town.score >= as_address.score + 2:
        return as_town
    if as_address.score >= as_town.score + 2:
        return as_address

    return AmbiguityDecision(
        label="AMBIGUOUS",
        score=max(as_town.score, as_address.score),
        reason=f"town={as_town.reason}|address={as_address.reason}",
        confidence=0.5,
    )
