"""Métriques de qualité du pipeline: fiabilité interne et précision dataset."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from src.models import CanonicalParty


def _norm(value: Optional[str]) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().upper().split())


def _geo_score(warnings: List[str], party: CanonicalParty) -> Tuple[float, str]:
    if any("pass1_town_confirmed_geonames:exact" in str(w) for w in warnings):
        return 1.0, "GeoNames exact"
    if any("pass1_town_confirmed_geonames:alternate" in str(w) for w in warnings):
        return 0.9, "GeoNames alternate"
    if any("pass1_town_confirmed_geonames:fuzzy" in str(w) for w in warnings):
        return 0.72, "GeoNames fuzzy"
    if party.country_town and party.country_town.country and party.country_town.town:
        return 0.6, "Geo inferred"
    if party.country_town and party.country_town.country:
        return 0.35, "Country only"
    return 0.0, "Geo missing"


def _country_town_parsing_score(warnings: List[str], party: CanonicalParty) -> Tuple[float, str, Dict[str, Any]]:
    geo = getattr(party, "country_town", None)
    country = _norm(geo.country if geo else None)
    town = _norm(geo.town if geo else None)

    details = {
        "country_present": bool(country),
        "town_present": bool(town),
        "country_value": country or None,
        "town_value": town or None,
    }

    if not country and not town:
        return 0.0, "Country and town missing", details
    if any("pass1_town_confirmed_geonames:exact" in str(w) for w in warnings):
        return 1.0, "Country and town confirmed (GeoNames exact)", details
    if any("pass1_town_confirmed_geonames:alternate" in str(w) for w in warnings):
        return 0.9, "Country and town confirmed (GeoNames alternate)", details
    if any("pass1_town_confirmed_geonames:fuzzy" in str(w) for w in warnings):
        return 0.78, "Country and town confirmed (GeoNames fuzzy)", details
    if any("pass2_town_backfilled_from_fragmentation:" in str(w) for w in warnings):
        return 0.72, "Town recovered from fragmentation", details
    if any("requires_manual_verification:town_unverified" in str(w) for w in warnings):
        return 0.25, "Town extracted but unverified", details
    if any("pass1_town_ambiguous_requires_disambiguation" in str(w) for w in warnings):
        return 0.2, "Town ambiguous", details
    if any("pass1_country_missing" in str(w) for w in warnings):
        return 0.15 if town else 0.0, "Country missing", details
    if country and town:
        return 0.65, "Country and town extracted", details
    if country:
        return 0.35, "Country extracted, town missing", details
    return 0.2, "Town extracted, country missing", details


def _address_score(party: CanonicalParty) -> Tuple[float, str]:
    validations = getattr(party, "address_validation", None) or []
    if not validations:
        return (0.65, "No address lines") if not party.address_lines else (0.35, "Address unvalidated")

    valid_count = sum(1 for item in validations if item.get("contextual_valid"))
    score = valid_count / max(1, len(validations))
    label = f"{valid_count}/{len(validations)} address lines valid"
    return score, label


def _fragmentation_score(party: CanonicalParty) -> Tuple[float, str]:
    fragments = getattr(party, "fragmented_addresses", []) or []
    if not fragments:
        return 0.0, "No fragmentation"
    best = max(float(getattr(frag, "fragmentation_confidence", 0.0) or 0.0) for frag in fragments)
    return best, f"Best fragment {best:.2f}"


def _decision_score(party: CanonicalParty) -> Tuple[float, str]:
    if getattr(party.meta, "rejected", False):
        return 0.0, "Rejected"
    warnings = list(getattr(party.meta, "warnings", []) or [])
    if any("requires_manual_verification" in str(w) for w in warnings):
        return 0.5, "Manual review"
    return 1.0, "Accepted"


def compute_reliability_score(party: CanonicalParty) -> Dict[str, Any]:
    """Score interne de fiabilité du résultat, sans vérité terrain."""
    parse_conf = float(getattr(party.meta, "parse_confidence", 0.0) or 0.0)
    warnings = list(getattr(party.meta, "warnings", []) or [])

    geo, geo_reason = _geo_score(warnings, party)
    geo_parse, geo_parse_reason, geo_parse_details = _country_town_parsing_score(warnings, party)
    addr, addr_reason = _address_score(party)
    frag, frag_reason = _fragmentation_score(party)
    decision, decision_reason = _decision_score(party)

    fallback_penalty = 0.03 if getattr(party.meta, "fallback_used", False) else 0.0
    warning_penalty = min(0.12, 0.01 * len(warnings))

    score = (
        0.40 * parse_conf
        + 0.22 * geo
        + 0.18 * addr
        + 0.12 * frag
        + 0.08 * decision
        - fallback_penalty
        - warning_penalty
    )
    score = max(0.0, min(1.0, round(score, 3)))

    if score >= 0.85:
        band = "Tres fiable"
    elif score >= 0.70:
        band = "Fiable"
    elif score >= 0.55:
        band = "Moyen"
    else:
        band = "Faible"

    return {
        "score": score,
        "percent": int(round(score * 100)),
        "band": band,
        "country_town_parsing": {
            "score": round(geo_parse, 3),
            "percent": int(round(geo_parse * 100)),
            "reason": geo_parse_reason,
            **geo_parse_details,
        },
        "components": {
            "parse_confidence": round(parse_conf, 3),
            "geo_score": round(geo, 3),
            "country_town_parsing_score": round(geo_parse, 3),
            "address_score": round(addr, 3),
            "fragmentation_score": round(frag, 3),
            "decision_score": round(decision, 3),
            "fallback_penalty": round(fallback_penalty, 3),
            "warning_penalty": round(warning_penalty, 3),
        },
        "reasons": {
            "geo": geo_reason,
            "country_town_parsing": geo_parse_reason,
            "address": addr_reason,
            "fragmentation": frag_reason,
            "decision": decision_reason,
        },
    }


def compare_party_to_ground_truth(party: CanonicalParty, truth: Dict[str, Any]) -> Dict[str, bool]:
    predicted_name = _norm(" ".join(party.name))
    truth_name = _norm(truth.get("name"))

    predicted_country = _norm(party.country_town.country if party.country_town else None)
    truth_country = _norm(truth.get("country"))

    predicted_town = _norm(party.country_town.town if party.country_town else None)
    truth_town = _norm(truth.get("town"))

    predicted_postal = _norm(party.country_town.postal_code if party.country_town else None)
    truth_postal = _norm(truth.get("postal_code"))

    predicted_address = _norm(" ".join(party.address_lines))
    truth_address = _norm(truth.get("address"))

    return {
        "name": (not truth_name) or predicted_name == truth_name,
        "country": (not truth_country) or predicted_country == truth_country,
        "town": (not truth_town) or predicted_town == truth_town,
        "postal_code": (not truth_postal) or predicted_postal == truth_postal,
        "address": (not truth_address) or predicted_address == truth_address,
    }


def compute_dataset_precision(
    evaluated_rows: Iterable[Tuple[CanonicalParty, Dict[str, Any]]],
) -> Dict[str, Any]:
    rows = list(evaluated_rows)
    if not rows:
        return {
            "count": 0,
            "field_accuracy": {},
            "exact_match_rate": 0.0,
        }

    field_hits = {
        "name": 0,
        "country": 0,
        "town": 0,
        "postal_code": 0,
        "address": 0,
    }
    exact_hits = 0

    for party, truth in rows:
        comp = compare_party_to_ground_truth(party, truth)
        for key in field_hits:
            field_hits[key] += 1 if comp[key] else 0
        if all(comp.values()):
            exact_hits += 1

    count = len(rows)
    field_accuracy = {key: round(value / count, 4) for key, value in field_hits.items()}

    return {
        "count": count,
        "field_accuracy": field_accuracy,
        "exact_match_rate": round(exact_hits / count, 4),
    }
