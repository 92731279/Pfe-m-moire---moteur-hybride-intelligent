"""e2_validator.py — Double validation sémantique : Pass1 geo + Pass2 adresse"""

from typing import Dict, Set, List, Optional, Tuple

from src.models import CanonicalParty
from src.reference_data import CITIES_BY_COUNTRY
from src.e2_address_parser import parse_address_line
from src.toponym_normalizer import (
    canonicalize_toponym, town_known_for_country,
    find_variant_match_in_address, toponyms_equivalent,
)

VALID_COUNTRIES: Set[str] = set(CITIES_BY_COUNTRY.keys())


def _norm(value: Optional[str]) -> str:
    if not value:
        return ""
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


# ============================================================
# PASS 1 — Validation géographique country / town
# ============================================================

def _validate_pass1_country_town(
    party: CanonicalParty,
) -> Tuple[str, str, bool]:
    """
    Vérifie :
    1. Le pays existe dans nos référentiels
    2. La ville existe
    3. La ville appartient bien au pays
    Retourne (country, town, geo_coherent)
    """
    warnings = party.meta.warnings
    geo = party.country_town

    country = _norm(geo.country) if geo else ""
    town = _norm(geo.town) if geo else ""
    geo_coherent = False

    # --- inférence pays depuis ville connue ---
    if not country and town:
        inferred = CITY_TO_COUNTRY.get(town)
        if inferred:
            geo.country = inferred
            country = inferred
            _append_warning_once(
                warnings, f"pass1_country_inferred_from_town:{town}→{inferred}"
            )
            party.meta.parse_confidence = min(
                party.meta.parse_confidence, 0.80
            )

    # --- validation pays ---
    if not country:
        _append_warning_once(warnings, "pass1_country_missing")
        party.meta.parse_confidence = min(party.meta.parse_confidence, 0.70)
    elif country not in VALID_COUNTRIES:
        _append_warning_once(warnings, f"pass1_unknown_country:{country}")
        party.meta.parse_confidence = min(party.meta.parse_confidence, 0.65)

    # --- validation ville ---
    if not town:
        _append_warning_once(warnings, "pass1_town_missing")
        party.meta.parse_confidence = min(party.meta.parse_confidence, 0.70)
    else:
        if country in CITIES_BY_COUNTRY:
            if town_known_for_country(country, town):
                # ✅ Ville connue pour ce pays → canonicaliser
                geo.town = canonicalize_toponym(geo.town)
                town = _norm(geo.town)
                geo_coherent = True
            else:
                # Chercher variante dans les adresses
                variant = find_variant_match_in_address(
                    party.address_lines, geo.town
                )
                if variant:
                    observed, canonical = variant
                    geo.town = canonical
                    town = _norm(canonical)
                    geo_coherent = True
                    _append_warning_once(
                        warnings,
                        f"pass1_town_variant_matched:{observed}→{canonical}",
                    )
                    party.meta.parse_confidence = min(
                        1.0,
                        round(max(party.meta.parse_confidence, 0.80), 2),
                    )
                else:
                    # ❌ Ville inconnue pour ce pays
                    _append_warning_once(
                        warnings,
                        f"pass1_town_not_in_country:{country}:{town}",
                    )
                    party.meta.parse_confidence = min(
                        party.meta.parse_confidence, 0.60
                    )
        else:
            # Pays pas dans notre référentiel de villes
            geo_coherent = bool(country and town)

    return country, town, geo_coherent


# ============================================================
# PASS 2 — Validation des lignes d'adresse
# ============================================================

def _validate_pass2_address_lines(
    party: CanonicalParty,
    country: str,
    town: str,
    geo_coherent: bool,
) -> List[Dict]:
    """
    Pour chaque address_line :
    1. libpostal : est-ce une vraie adresse ?
    2. Cohérence avec town/country déjà validés en Pass1
    3. Détection doublons ville/pays dans les lignes
    """
    warnings = party.meta.warnings
    results: List[Dict] = []

    if not party.address_lines:
        # Absence d'adresse acceptable si on a country + town
        if not (country and town):
            _append_warning_once(warnings, "pass2_address_missing")
            party.meta.parse_confidence = min(
                party.meta.parse_confidence, 0.80
            )
        return results

    valid_count = 0

    for line in party.address_lines:

        parsed = parse_address_line(line)
        components = parsed.get("components", {}) or {}

        # --- Critère 1 : libpostal valide intrinsèquement ---
        intrinsic_valid = bool(parsed.get("is_valid"))

        # --- Critère 2 : composants clés présents ---
        key_labels = {"road", "house_number", "unit", "po_box", "house"}
        locally_plausible = bool(set(components.keys()) & key_labels)

        # --- Critère 3 : cohérence avec town/country (Pass1) ---
        # On vérifie si la ligne contient des éléments
        # COHÉRENTS avec la géo validée en Pass1
        geo_consistent = _check_address_geo_consistency(
            components, line, town, country, geo_coherent
        )

        # --- Critère 4 : doublon ville/pays dans la ligne ---
        contains_town_or_country = _line_contains_town_or_country(
            line, town, country
        )

        contextual_valid = (
            intrinsic_valid or locally_plausible or geo_consistent
        )

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
                _append_warning_once(
                    warnings,
                    f"pass2_address_contains_town_or_country:{line}",
                )
            if not intrinsic_valid:
                _append_warning_once(
                    warnings,
                    f"pass2_address_contextually_accepted:{line}",
                )
        else:
            _append_warning_once(
                warnings, f"pass2_invalid_address_line:{line}"
            )
            party.meta.parse_confidence = min(
                party.meta.parse_confidence, 0.70
            )

        # Warnings libpostal soft
        for w in parsed.get("warnings", []):
            if w == "missing_road_like_component" and contextual_valid:
                _append_warning_once(warnings, f"pass2_soft:{w}")
            else:
                _append_warning_once(warnings, f"pass2_libpostal:{w}")

    # Si aucune adresse valide détectée
    if valid_count == 0 and party.address_lines:
        _append_warning_once(warnings, "pass2_no_valid_address_detected")
        party.meta.parse_confidence = min(party.meta.parse_confidence, 0.55)

    # Si géo incohérente ET adresses présentes → pénalité
    if not geo_coherent and party.address_lines:
        _append_warning_once(
            warnings, "pass2_geo_incoherent_cannot_validate_address"
        )
        party.meta.parse_confidence = min(party.meta.parse_confidence, 0.60)

    return results


def _check_address_geo_consistency(
    components: Dict,
    raw_line: str,
    town: str,
    country: str,
    geo_coherent: bool,
) -> bool:
    """
    Vérifie si la ligne d'adresse est cohérente
    avec le town/country validés en Pass1.
    
    Logique hiérarchique :
    - Si Pass1 a validé geo_coherent → on fait confiance au contexte
    - Sinon on vérifie si libpostal trouve city/country cohérents
    """
    if not town and not country:
        return False

    town_n = _norm(town)
    country_n = _norm(country)

    parsed_city = _norm(str(components.get("city", "")))
    parsed_country = _norm(str(components.get("country", "")))
    parsed_state = _norm(str(components.get("state", "")))

    # Si libpostal détecte une ville → cohérente avec town validé ?
    if parsed_city and town_n:
        if toponyms_equivalent(parsed_city, town_n):
            return True

    # Si libpostal détecte un pays → cohérent avec country validé ?
    if parsed_country and country_n:
        if parsed_country == country_n:
            return True

    # Si libpostal détecte un état → cohérent avec town ?
    if parsed_state and town_n:
        if toponyms_equivalent(parsed_state, town_n):
            return True

    # Si geo_coherent (Pass1 OK) → on accepte l'adresse
    # même si libpostal ne trouve pas city/country dedans
    # (cas normal : "FRIEDRICHSTRASSE 10" ne contient pas "BERLIN")
    if geo_coherent:
        return True

    return False


def _line_contains_town_or_country(
    line: str, town: str, country: str
) -> bool:
    """
    Détecte si une ligne d'adresse contient
    la ville ou le pays (doublon à signaler).
    Ex: "FRIEDRICHSTRASSE 10 BERLIN" → True
    Ex: "FRIEDRICHSTRASSE 10" → False
    """
    line_n = _norm(line)
    if town and _norm(town) in line_n:
        return True
    if country and _norm(country) in line_n:
        return True
    return False


# ============================================================
# Fonction principale
# ============================================================

def validate_party_semantics(party: CanonicalParty) -> CanonicalParty:
    """
    Validation en 2 passes :
    Pass 1 → cohérence géographique (country / town)
    Pass 2 → cohérence des lignes d'adresse avec la géo validée
    """
    warnings = party.meta.warnings

    if party.country_town is None:
        _append_warning_once(warnings, "pass1_missing_country_town")
        party.meta.parse_confidence = min(party.meta.parse_confidence, 0.60)
        party.address_validation = []
        return party

    # ---- PASS 1 : géographie ----
    country, town, geo_coherent = _validate_pass1_country_town(party)

    # ---- PASS 2 : adresses ----
    address_results = _validate_pass2_address_lines(
        party, country, town, geo_coherent
    )

    party.address_validation = address_results
    return party