"""e2_validator.py — Double validation sémantique: Pass1 geo + Pass2 adresse"""
import re  # ✅ À ajouter en premier

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
    from src.geonames.geonames_db import find_place, find_alternate_place, resolve_locality_hierarchy
    GEONAMES_AVAILABLE = True
    print("✅ GeoNames disponible pour validation")
except ImportError:
    GEONAMES_AVAILABLE = False
    print("⚠️ GeoNames non disponible (fallback toponymie)")

VALID_COUNTRIES: Set[str] = set(COUNTRY_CODES)

def _norm(value: Optional[str]) -> str:
    if not value: return ""
    return " ".join(value.strip().upper().split())

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


def _infer_town_from_address_lines(country: str, address_lines: List[str]) -> Optional[str]:
    if not country or not address_lines:
        return None

    known_cities = CITIES_BY_COUNTRY.get(country, []) or []
    if not known_cities:
        return None

    normalized_candidates = []
    for city in known_cities:
        city_n = canonicalize_toponym(_norm(city))
        if city_n:
            normalized_candidates.append(city_n)

    for line in address_lines:
        line_n = canonicalize_toponym(_norm(line))
        if not line_n:
            continue
        for city_n in normalized_candidates:
            pattern = rf"(?:^|\b){re.escape(city_n)}(?:\b|$)"
            if re.search(pattern, line_n):
                return city_n
    return None


def _prefer_input_town_when_canonical_expands(town_raw: str, canonical: Optional[str]) -> str:
    if not town_raw or not canonical:
        return canonical or town_raw

    raw_n = _norm(town_raw)
    can_n = _norm(canonical)
    if not raw_n or not can_n or raw_n == can_n:
        return can_n or raw_n

    raw_tokens = set(raw_n.split())
    can_tokens = set(can_n.split())
    if not raw_tokens or not can_tokens:
        return can_n

    # Keep the input form when canonical only adds directional qualifiers.
    directional_tokens = {
        "NORD", "SUD", "EST", "OUEST", "NORTH", "SOUTH", "EAST", "WEST",
        "N", "S", "E", "W",
    }
    added_tokens = can_tokens - raw_tokens
    if raw_tokens.issubset(can_tokens) and added_tokens and added_tokens.issubset(directional_tokens):
        return raw_n

    return can_n


def _resolve_town_from_composite(country: str, town_source: str) -> Optional[Tuple[str, str]]:
    """Try to resolve a composite locality (suburb + city) to an official city via GeoNames."""
    if not GEONAMES_AVAILABLE or not country or not town_source:
        return None

    parts: List[str] = []
    split_parts = [token for token in re.split(r"[,/;]", town_source) if token and token.strip()]
    for token in reversed(split_parts):
        clean = canonicalize_toponym(_norm(token))
        if clean and not re.search(r"\d", clean):
            parts.append(clean)

    collapsed = canonicalize_toponym(_norm(town_source))
    if collapsed:
        tokens = collapsed.split()
        for size in range(min(3, len(tokens)), 0, -1):
            for start in range(0, len(tokens) - size + 1):
                candidate = " ".join(tokens[start:start + size])
                if candidate and not re.search(r"\d", candidate):
                    parts.append(candidate)

    seen = set()
    for candidate in parts:
        candidate_n = _norm(candidate)
        if not candidate_n or candidate_n in seen:
            continue
        seen.add(candidate_n)
        is_valid, canonical, matched_via = validate_town_in_country(country, candidate_n)
        if is_valid and canonical and matched_via:
            chosen = _prefer_input_town_when_canonical_expands(candidate_n, canonical)
            return _norm(chosen), matched_via

    return None


def _looks_like_local_script_town(country: str, town: str) -> bool:
    if not country or not town:
        return False
    country = _norm(country)
    town = _norm(town)
    cjk_countries = {"CN", "JP", "KR", "TW", "HK"}
    arabic_script_countries = {"MA", "DZ", "TN", "EG", "SA", "AE", "QA", "KW", "BH", "OM", "JO", "LB", "SY", "IQ", "YE", "LY", "SD", "PS"}
    cyrillic_countries = {"RU", "UA", "BY", "BG", "RS", "MK", "ME", "KZ", "KG", "TJ", "UZ", "MN"}
    devanagari_countries = {"IN", "NP"}

    if country not in (cjk_countries | arabic_script_countries | cyrillic_countries | devanagari_countries):
        return False
    if re.search(r"\d", town):
        return False

    script_patterns = []
    if country in cjk_countries:
        script_patterns.append(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")
    if country in arabic_script_countries:
        script_patterns.append(r"[\u0600-\u06FF]")
    if country in cyrillic_countries:
        script_patterns.append(r"[\u0400-\u04FF]")
    if country in devanagari_countries:
        script_patterns.append(r"[\u0900-\u097F]")

    return any(bool(re.search(pattern, town)) for pattern in script_patterns)

# ============================================================
# PASS 1 — Validation géographique country/town
# ============================================================



def _validate_pass1_country_town(party: CanonicalParty) -> Tuple[str, str, bool, bool]:
    """
    Validation stricte pays/ville.
    Priorité: GeoNames. Si GeoNames valide la ville, on accepte et on résout la hiérarchie (ex: Enfidha → Sousse).
    Sinon, si un contexte suburb est détecté, on bloque.
    """
    warnings = party.meta.warnings
    geo = party.country_town
    country = _norm(geo.country) if geo else ""
    town_source = _norm(geo.town) if geo else ""
    town_raw = canonicalize_toponym(town_source) if geo else ""

    # 1. 🔍 Détection du contexte "suburb/quartier" dans les lignes d'adresse brutes
    SUBURB_KEYWORDS = {"CITE", "CITÉ", "ZONE", "QUARTIER", "SECTEUR", "IMMEUBLE", "IMM", "LOTISSEMENT"}
    has_suburb_context = any(
        any(kw in line.upper() for kw in SUBURB_KEYWORDS)
        for line in (party.address_lines or [])
    )
    is_town_literally_a_suburb = any(kw in town_raw.upper() for kw in SUBURB_KEYWORDS)


    # 2. ✅ Validation GeoNames PRIORITAIRE (si la ville existe, on la garde / la promeut)
    if GEONAMES_AVAILABLE and country and town_raw:
        is_valid, canonical, matched_via = validate_town_in_country(country, town_raw)
        if is_valid and matched_via and not is_town_literally_a_suburb:

            if matched_via == "district_promotion":
                chosen_town = canonical.upper() if canonical else town_raw
            else:
                chosen_town = _prefer_input_town_when_canonical_expands(town_raw, canonical)
                
            _append_warning_once(warnings, f"pass1_town_confirmed_geonames:{matched_via}")
            if has_suburb_context:
                _append_warning_once(warnings, "pass1_town_extracted_from_suburb_and_confirmed")
            
            # ✅ CORRECTION: Nettoyage des alertes de blocage précédentes si on a récupéré une ville (ex: Post-SLM ou Post-Fragment)
            warnings[:] = [w for w in warnings if "requires_manual_verification" not in str(w)]
            
            # ✅ CORRECTION: Conserver la localité exacte (ex: Douar Hicher) au lieu de promouvoir!
            if matched_via != "district_promotion":
                parent_town = resolve_locality_hierarchy(country, town_raw)
                if parent_town and parent_town.upper() != _norm(chosen_town):
                    # C'est une localité avec un parent administratif, mais on garde la localité précise
                    warnings.append(f"pass1_locality_has_parent:{chosen_town}→{parent_town}")
                    return country, _norm(chosen_town), True, False
            
            return country, _norm(chosen_town), True, False
        else:
            _append_warning_once(warnings, f"pass1_town_not_official:{town_raw}")

            composite_resolution = _resolve_town_from_composite(country, town_source or town_raw)
            if composite_resolution:
                resolved_town, matched_via = composite_resolution
                _append_warning_once(warnings, f"pass1_town_resolved_from_composite:{town_raw}->{resolved_town}:{matched_via}")
                warnings[:] = [w for w in warnings if "requires_manual_verification" not in str(w)]
                return country, resolved_town, True, False

            if _looks_like_local_script_town(country, town_raw):
                _append_warning_once(warnings, "pass1_town_local_script_accepted")
                warnings[:] = [w for w in warnings if "requires_manual_verification" not in str(w)]
                return country, town_raw, True, False
            inferred_town = _infer_town_from_address_lines(country, party.address_lines or [])
            if inferred_town:
                _append_warning_once(warnings, f"pass1_town_inferred_from_address:{inferred_town}")
                warnings[:] = [w for w in warnings if "requires_manual_verification" not in str(w)]
                return country, inferred_town.upper(), True, False
            if is_town_literally_a_suburb:
                _append_warning_once(warnings, "pass1_town_is_suburb_keyword_rejected")
                _append_warning_once(warnings, "requires_manual_verification:suburb_cannot_be_promoted_to_city")
                party.meta.parse_confidence = min(party.meta.parse_confidence, 0.40)
                return country, None, False, True
            if has_suburb_context:
                _append_warning_once(warnings, "pass1_suburb_context_detected_and_town_invalid")
                _append_warning_once(warnings, "requires_manual_verification:suburb_cannot_be_promoted_to_city")
                party.meta.parse_confidence = min(party.meta.parse_confidence, 0.40)
                return country, None, False, True
            _append_warning_once(warnings, "requires_manual_verification:town_unverified")
            return country, None, False, True

    # 3. 🚫 BLOCAGE STRICT si contexte suburb détecté et pas de ville
    if has_suburb_context:
        warnings.append("pass1_suburb_context_detected")
        warnings.append("requires_manual_verification:suburb_cannot_be_promoted_to_city")
        party.meta.parse_confidence = min(party.meta.parse_confidence, 0.40)
        return country, None, False, True  # town=None, is_ambiguous=True → Quarantaine

    elif not country:
        warnings.append("pass1_country_missing")
        return country, None, False, True

    if not town_raw:
        warnings.append("town_missing")
        return country, None, False, True

    # Fallback safe : on garde la valeur brute
    return country, town_raw, True, False
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
        key_labels = {"road", "house_number", "unit", "po_box", "house", "suburb", "city_district"}
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
        
        if contextual_valid:
            valid_count += 1
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
    line_n = _norm(re.sub(r"[^A-Z0-9]+", " ", line or ""))
    if not line_n:
        return False

    town_n = _norm(re.sub(r"[^A-Z0-9]+", " ", town or ""))
    if town_n:
        if re.search(rf"(?:^|\s){re.escape(town_n)}(?:\s|$)", line_n):
            return True

    country_n = _norm(re.sub(r"[^A-Z0-9]+", " ", country or ""))
    if country_n:
        if re.search(rf"(?:^|\s){re.escape(country_n)}(?:\s|$)", line_n):
            return True

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
