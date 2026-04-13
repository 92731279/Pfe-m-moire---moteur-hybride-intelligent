"""rejection_policy.py — Décision métier acceptation/rejet des messages parsés"""

from typing import List

from src.models import CanonicalParty


def _append_once(items: List[str], value: str) -> None:
    if value not in items:
        items.append(value)


def apply_rejection_policy(party: CanonicalParty) -> CanonicalParty:
    """
    Marque le message comme rejeté si les éléments métier minimaux sont absents.
    Règle actuelle pour champs libres 50K/59:
    - nom obligatoire
    - pays obligatoire
    - au moins une localisation exploitable: ville OU adresse
    """
    reasons: List[str] = []

    has_name = bool(party.name and any((x or "").strip() for x in party.name))
    has_country = bool(party.country_town and party.country_town.country)
    has_town = bool(party.country_town and party.country_town.town)
    has_address = bool(party.address_lines)

    if not has_name:
        _append_once(reasons, "mandatory_missing:name")
    if not has_country:
        _append_once(reasons, "mandatory_missing:country")

    if party.field_type in {"50K", "59", "50F", "59F"}:
        if not (has_town or has_address):
            _append_once(reasons, "mandatory_missing:town_or_address")

    party.meta.rejected = bool(reasons)
    party.meta.rejection_reasons = reasons
    return party
