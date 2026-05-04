"""rejection_policy.py — Décision métier stricte : Acceptation ou Rejet/Quarantaine"""
from typing import List
from src.models import CanonicalParty

def _append_once(items: List[str], value: str) -> None:
    if value not in items:
        items.append(value)


def apply_rejection_policy(party: CanonicalParty) -> CanonicalParty:
    """
    Politique de rejet/acceptation stricte.
    
    Rejette les messages SI:
    1. Validation SLM strict a échoué
    2. Vérification manuelle explicitement requise
    3. Composants obligatoires manquants (nom, ville, pays)
    4. Confiance trop faible (< 0.60)
    
    **Important**: Les patterns suspects (ex: ville courte) ne causent PAS automatiquement
    un rejet, mais plutôt une ALERTE ET UN FLAG pour révision manuelle.
    """
    reasons: List[str] = []
    warnings = list(getattr(party.meta, 'warnings', []) or [])
    confidence = float(getattr(party.meta, 'parse_confidence', 0.0) or 0.0)
    
    # ========== NIVEAU 0: VALIDATION SLM STRICTE (priorité absolue) ==========
    # 🚫 Si le SLM a échoué la validation stricte, REJETER
    if any("slm_validation_failed_strict" in str(w) for w in warnings):
        reasons.append("slm_validation_failed:fallback_results_unverified")
    
    # ========== NIVEAU 1: VÉRIFICATION MANUELLE EXPLICITE ==========
    if any("requires_manual_verification" in str(w) for w in warnings):
        reasons.append("quarantine_manual_review_required")
    
    # ========== NIVEAU 2: COMPOSANTS OBLIGATOIRES ==========
    # Ville obligatoire
    if not party.country_town or not party.country_town.town:
        reasons.append("mandatory_missing:town")
    
    # Nom obligatoire  
    if not party.name or all(not n for n in party.name):
        reasons.append("mandatory_missing:name")
    
    # Pays obligatoire
    if not party.country_town or not party.country_town.country:
        reasons.append("mandatory_missing:country")
    
    # ========== NIVEAU 3: VALIDATION DE CONFIANCE ==========
    # Confiance minimale: 0.60
    if confidence < 0.60:
        if not reasons:
            reasons.append(f"low_confidence:{confidence}")
        else:
            reasons.append(f"low_confidence_with_other_issues:{confidence}")
    
    # ========== NIVEAU 4: FLAGS POUR RÉVISION MANUELLE (pas rejection!) ==========
    # Ces patterns ne causent pas de rejection, mais déclenchent un flag de révision
    party.meta.requires_manual_review = False
    
    town = (party.country_town.town or "").strip().upper() if party.country_town else ""
    postal = (party.country_town.postal_code or "").strip().upper() if party.country_town else ""
    
    # Pattern suspect: town < 3 caractères (sauf codes acceptés)
    KNOWN_SHORT_CITIES = {"NY", "SF", "LA", "DC", "UK", "GB"}
    if town and len(town) < 3 and town not in KNOWN_SHORT_CITIES:
        # Alert but don't reject - let manual review decide
        party.meta.requires_manual_review = True
        if "pass2_town_suspiciously_short" not in " ".join(str(w) for w in warnings):
            # Add this as a warning if not already present
            warnings.append(f"alert:town_suspiciously_short:{town}")
    
    # Pattern suspect: town et postal_code semblent swappés
    # (ex: town="NEW" et postal="YORK" où les deux sont des mots d'une ville)
    # Mais SEULEMENT si la town n'a été trouvée nulle part (pas confirmée par GeoNames)
    if town and len(town) < 4 and postal and not any(c.isdigit() for c in postal[:2]):
        is_town_confirmed = any("town_confirmed" in str(w) for w in warnings)
        if is_town_confirmed:
            # GeoNames a confirmé cette ville, donc pas de problème (ex: "NEW YORK" parsed correctement)
            pass
        else:
            # GeoNames n'a pas confirmé, et le pattern est suspect
            party.meta.requires_manual_review = True
            if "CRITICAL_town_postal_swap" not in " ".join(str(w) for w in warnings):
                warnings.append(f"alert:possible_town_postal_swap:{town}|{postal}")
    
    # Pattern suspect: confiance modérée (0.65-0.79) avec ambiguité
    if 0.65 <= confidence < 0.80:
        has_ambiguity = any(
            "ambiguous" in str(w).lower() or 
            "incoherent" in str(w).lower()
            for w in warnings
        )
        if has_ambiguity:
            party.meta.requires_manual_review = True
    
    # Pattern suspect: geo-incoherence avec confiance < 0.75
    has_geo_incoherence = any(
        "geo_incoherent" in str(w).lower() or
        "cannot_validate_address" in str(w).lower()
        for w in warnings
    )
    if has_geo_incoherence and confidence < 0.75:
        party.meta.requires_manual_review = True
    
    # ========== FINALE: DÉCISION ==========
    party.meta.rejected = bool(reasons)
    party.meta.rejection_reasons = reasons
    return party