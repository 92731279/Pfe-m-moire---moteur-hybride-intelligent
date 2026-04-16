"""rejection_policy.py — Décision métier stricte : Acceptation ou Rejet/Quarantaine"""
from typing import List
from src.models import CanonicalParty

def _append_once(items: List[str], value: str) -> None:
    if value not in items:
        items.append(value)

def apply_rejection_policy(party: CanonicalParty) -> CanonicalParty:
    """
    Règle SR2026 stricte :
    - <Ctry> obligatoire
    - <TwnNm> obligatoire
    Si la ville est absente ou ambiguë → REJET immédiat. Pas de fallback capitale.
    """
    reasons: List[str] = []
    
    has_name = bool(party.name and any((x or "").strip() for x in party.name))
    has_country = bool(party.country_town and party.country_town.country)
    has_town = bool(
        party.country_town 
        and party.country_town.town 
        and party.country_town.town not in {None, "AMBIGUOUS", "UNKNOWN", "NULL"}
    )

    if not has_name:
        _append_once(reasons, "mandatory_missing:name")
    if not has_country:
        _append_once(reasons, "mandatory_missing:country")
        
    # ⛔ STRICT : Si la ville n'est pas validée ou est ambiguë → REJET
    if not has_town:
        _append_once(reasons, "rejected_missing_or_ambiguous_town")

    party.meta.rejected = bool(reasons)
    party.meta.rejection_reasons = reasons
    return party