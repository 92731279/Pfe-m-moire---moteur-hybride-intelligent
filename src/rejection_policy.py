"""rejection_policy.py — Décision métier stricte : Acceptation ou Rejet/Quarantaine"""
from typing import List
from src.models import CanonicalParty

def _append_once(items: List[str], value: str) -> None:
    if value not in items:
        items.append(value)


def apply_rejection_policy(party: CanonicalParty) -> CanonicalParty:
    reasons: List[str] = []
    
    # ✅ Priorité : Détection explicite du besoin de vérification manuelle
    if any("requires_manual_verification" in str(w) for w in party.meta.warnings):
        reasons.append("quarantine_manual_review_required")
    elif not party.country_town or not party.country_town.town:
        reasons.append("mandatory_missing:town")
        
    if not party.name or all(not n for n in party.name):
        reasons.append("mandatory_missing:name")
    if not party.country_town or not party.country_town.country:
        reasons.append("mandatory_missing:country")

    party.meta.rejected = bool(reasons)
    party.meta.rejection_reasons = reasons
    return party