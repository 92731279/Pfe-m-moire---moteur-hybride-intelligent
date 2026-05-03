"""slm_validation.py — Validation backend des villes proposées par le SLM.

Le SLM ne doit jamais être affiché comme correct sans confirmation backend.
Cette couche valide la ville proposée contre les référentiels GeoNames et,
si disponible, contre le code postal canonique du dictionnaire.
"""

from __future__ import annotations

from typing import Optional, Tuple

from src.geonames.geonames_db import infer_city_from_postal_code
from src.geonames.geonames_validator import validate_town_in_country
from src.toponym_normalizer import toponyms_equivalent


def validate_slm_town(
    country_code: Optional[str],
    town: Optional[str],
    postal_code: Optional[str] = None,
) -> Tuple[Optional[str], str]:
    """Validate a town proposed by SLM before it is accepted.

    Returns:
        (validated_town, reason)
        validated_town is None when the SLM result must be rejected.
    """
    if not country_code or not town:
        return None, "missing_inputs"

    country = str(country_code).upper().strip()
    candidate = str(town).strip()
    if not country or not candidate:
        return None, "missing_inputs"

    postal = str(postal_code).strip() if postal_code else None
    if postal:
        canonical_postal_city = infer_city_from_postal_code(country, postal)
        if canonical_postal_city:
            if toponyms_equivalent(candidate, canonical_postal_city):
                return canonical_postal_city.upper(), "postal_match"
            return None, f"postal_mismatch:{canonical_postal_city}"

    is_valid, canonical, matched_via = validate_town_in_country(country, candidate)
    if is_valid and canonical:
        return canonical.upper(), f"geonames:{matched_via or 'unknown'}"

    return None, "not_geonames"