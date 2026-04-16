"""e2_validator.py — Double validation sémantique: Pass1 geo + Pass2 adresse"""

from typing import Dict, Set, List, Optional, Tuple
from src.models import CanonicalParty
from src.reference_data import CITIES_BY_COUNTRY, COUNTRY_CODES
from src.e2_address_parser import parse_address_line
from src.toponym_normalizer import (
    canonicalize_toponym, town_known_for_country, find_variant_match_in_address, reduce_to_known_core_toponym, toponyms_equivalent,
)

# Import GeoNames avec gestion d'erreur
try:
    from src.geonames.geonames_validator import validate_town_in_country
    from src.geonames.geonames_db import find_place, find_alternate_place
    GEONAMES_AVAILABLE = True
    print("✅ GeoNames disponible pour validation")
except ImportError:
    GEONAMES_AVAILABLE = False
    print("⚠️ GeoNames non disponible (fallback toponymie)")

VALID_COUNTRIES: Set[str] = set(COUNTRY_CODES)

def _norm(value: Optional[str]) -> str:
    if not value: return ""
    return "".join(value.strip().upper().split())

def _append_warning_once(warnings: List[str], warning: str) -> None:
    if warning not in warnings:
        warnings.append(warning)

def _build_city_to_country_index() -> Dict[str, str]:
    index: Dict[str, str] = {}
    for country, cities in CITIES_BY_COUNTRY.items():
        for city in cities:
            norm_city = _norm(city)
            if norm_city and norm_city not in index:
                index[norm_city] = country
    return index

CITY_TO_COUNTRY = _build_city_to_country_index()

# ============================================================
# PASS 1 — Validation géographique country/town
# ============================================================
def _validate_pass1_country_town(party: CanonicalParty) -> Tuple[str, str, bool, bool]:
    """
    Validation stricte pays/ville (Conformité SR2026).
    - Ne tronque AUCUN préfixe (Cité, Zone, Quartier...)
    - Valide UNIQUEMENT sur preuve forte (GeoNames exact/alternate)
    - Si localité/quartier ambigu sans ville parente explicite → town=None + WARNING
    """
    warnings = party.meta.warnings
    geo = party.country_town
    country = _norm(geo.country) if geo else ""
    town_raw = _norm(geo.town) if geo else ""
    
    # Liste des localités/quartiers connus comme ambigus (à enrichir via config ou DB)
    # Ces zones ne sont PAS des villes administratives ISO 20022 valides sans contexte explicite
    AMBIGUOUS_LOCALITIES = {
        "TN": {"ERRIADH", "ENFIDHA", "MORNAG", "RAOUED", "EL_OMRANE", "CITE_EL_KHADRA", "SIDI_HASSINE"},
        "FR": {"LA_DEFENSE", "SACLAY", "VILLEPINTE"},
    }
    
    is_ambiguous = False
    geo_coherent = False
    town = town_raw  # Par défaut, on garde la valeur brute

    # 1. Règle stricte : Détection de localité/quartier ambigu
    if country in AMBIGUOUS_LOCALITIES and town_raw in AMBIGUOUS_LOCALITIES[country]:
        _append_warning_once(warnings, f"ambiguous_suburb_detected:{town_raw}")
        return country, None, False, True  # ✅ town=None force l'absence de ville administrative

    # 2. Résolution GeoNames (uniquement si pas ambigu)
    if GEONAMES_AVAILABLE and country and town_raw:
        is_valid, canonical, matched_via = validate_town_in_country(country, town_raw)
        
        # Accepte uniquement match exact ou nom alternatif officiel
        if is_valid and matched_via in {"exact", "alternate"}:
            town = canonical
            geo_coherent = True
            _append_warning_once(warnings, f"pass1_town_confirmed_geonames:{matched_via}")
        else:
            # GeoNames ne trouve pas de ville officielle → ambiguë ou inconnue
            _append_warning_once(warnings, f"pass1_town_not_official_city:{town_raw}")
            is_ambiguous = True
            town = None  # ⛔ On ne devine pas. On vide le champ.
    elif not country:
        _append_warning_once(warnings, "pass1_country_missing")
        party.meta.parse_confidence = min(party.meta.parse_confidence, 0.60)

    return country, town, geo_coherent, is_ambiguous


# ============================================================
# PASS 2 — Validation des lignes d'adresse
# ============================================================
def _validate_pass2_address_lines(party: CanonicalParty, country: str, town: str, geo_coherent: bool) -> List[Dict]:
    """
    Pour chaque address_line:
    1. libpostal: est-ce une vraie adresse?
    2. Cohérence avec town/country déjà validés en Pass1
    """
    warnings = party.meta.warnings
    results: List[Dict] = []
    
    if not party.address_lines:
        if not (country and town):
            _append_warning_once(warnings, "pass2_address_missing")
            party.meta.parse_confidence = min(party.meta.parse_confidence, 0.80)
        return results

    valid_count = 0
    for line in party.address_lines:
        parsed = parse_address_line(line)
        components = parsed.get("components", {}) or {}

        intrinsic_valid = bool(parsed.get("is_valid"))
        key_labels = {"road", "house_number", "unit", "po_box", "house"}
        locally_plausible = bool(set(components.keys()) & key_labels)
        
        geo_consistent = _check_address_geo_consistency(components, line, town, country, geo_coherent)
        contains_town_or_country = _line_contains_town_or_country(line, town, country)
        
        contextual_valid = (intrinsic_valid or locally_plausible or geo_consistent)
        
        result = {
            **parsed,
            "pass": 2,
            "contextual_valid": contextual_valid,
            "contextual_checks": {
                "intrinsic_valid": intrinsic_valid,
                "locally_plausible": locally_plausible,
                "geo_consistent_with_pass1": geo_consistent,
                "contains_town_or_country": contains_town_or_country,
                "geo_coherent_pass1": geo_coherent,
                "town": town,
                "country": country,
            },
        }
        results.append(result)
        
        if contextual_valid: valid_count += 1
        if contains_town_or_country:
            _append_warning_once(warnings, f"pass2_address_contains_town_or_country:{line}")
        if not intrinsic_valid:
            _append_warning_once(warnings, f"pass2_address_contextually_accepted:{line}")
        else:
            _append_warning_once(warnings, f"pass2_invalid_address_line:{line}")
            party.meta.parse_confidence = min(party.meta.parse_confidence, 0.70)

        for w in parsed.get("warnings", []):
            if w == "missing_road_like_component" and contextual_valid:
                _append_warning_once(warnings, f"pass2_soft:{w}")
            else:
                _append_warning_once(warnings, f"pass2_libpostal:{w}")

    if valid_count == 0 and party.address_lines:
        _append_warning_once(warnings, "pass2_no_valid_address_detected")
        party.meta.parse_confidence = min(party.meta.parse_confidence, 0.55)
        
    if not geo_coherent and party.address_lines:
        _append_warning_once(warnings, "pass2_geo_incoherent_cannot_validate_address")
        party.meta.parse_confidence = min(party.meta.parse_confidence, 0.60)
        
    return results

def _check_address_geo_consistency(components: Dict, raw_line: str, town: str, country: str, geo_coherent: bool) -> bool:
    if not town and not country: return False
    town_n = _norm(town)
    country_n = _norm(country)
    
    parsed_city = _norm(str(components.get("city", "")))
    parsed_country = _norm(str(components.get("country", "")))
    parsed_state = _norm(str(components.get("state", "")))
    
    if parsed_city and town_n:
        if toponyms_equivalent(parsed_city, town_n): return True
    if parsed_country and country_n:
        if parsed_country == country_n: return True
    if parsed_state and town_n:
        if toponyms_equivalent(parsed_state, town_n): return True
        
    if geo_coherent: return True
    return False

def _line_contains_town_or_country(line: str, town: str, country: str) -> bool:
    line_n = _norm(line)
    if town and _norm(town) in line_n: return True
    if country and _norm(country) in line_n: return True
    return False

# ============================================================
# Fonction principale
# ============================================================
def validate_party_semantics(party: CanonicalParty) -> CanonicalParty:
    """Validation en 2 passes: Pass 1 → géo, Pass 2 → adresses"""
    warnings = party.meta.warnings
    
    if party.country_town is None:
        _append_warning_once(warnings, "pass1_missing_country_town")
        party.meta.parse_confidence = min(party.meta.parse_confidence, 0.60)
        party.address_validation = []
        return party

    # ✅ CORRECTION : Gestion des 4 valeurs retournées (country, town, geo_coherent, is_ambiguous)
    country, town, geo_coherent, is_ambiguous = _validate_pass1_country_town(party)
    
    if is_ambiguous:
        # Si la ville est ambiguë (ex: Erriadh), on pénalise la confiance
        _append_warning_once(warnings, "pass1_town_ambiguous_requires_disambiguation")
        party.meta.parse_confidence = min(party.meta.parse_confidence, 0.65)
        # On peut aussi forcer un fallback SLM ici si nécessaire, mais la pénalité suffit souvent

    # Mise à jour de l'objet party avec la ville résolue
    if party.country_town:
        party.country_town.town = town

    # Pass 2
    address_results = _validate_pass2_address_lines(party, country, town, geo_coherent)
    party.address_validation = address_results
    
    return party