"""
geonames_validator.py
Validation géographique mondiale via GeoNames.
3 niveaux de recherche pour maximiser la fiabilité.
"""

import re
import unicodedata
from typing import Optional, Tuple
from src.geonames.geonames_db import (
    find_place, find_alternate_place, find_place_fuzzy
)


def _normalize(value: Optional[str]) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFD", value)
    value = "".join(
        ch for ch in value if unicodedata.category(ch) != "Mn"
    )
    value = value.upper().strip()
    value = re.sub(r"\s+", " ", value)
    return value


def validate_town_in_country(
    country_code: str,
    town_name: str,
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Validation mondiale en 4 niveaux :

    Niveau 1 : Recherche exacte (name / asciiname)
    Niveau 2 : Recherche via noms alternatifs
    Niveau 3 : Recherche avec variantes générées
    Niveau 4 : Recherche approximative LIKE

    Retourne (is_valid, canonical_name, matched_via)
    """
    if not country_code or not town_name:
        return False, None, None

    town_n = _normalize(town_name)

    # --- Niveau 1 : Recherche exacte ---
    result = find_place(country_code, town_n)
    if result:
        return True, result["name"], "exact"

    # --- Niveau 2 : Noms alternatifs ---
    result = find_alternate_place(country_code, town_n)
    if result:
        return True, result["name"], "alternate"

    # --- Niveau 3 : Variantes générées ---
    for variant in _generate_variants(town_n):
        result = find_place(country_code, variant)
        if result:
            return True, result["name"], f"variant_exact:{variant}"

        result = find_alternate_place(country_code, variant)
        if result:
            return True, result["name"], f"variant_alternate:{variant}"

    # --- Niveau 4 : Recherche approximative LIKE ---
    # Seulement si le nom est assez long (évite les faux positifs)
    if len(town_n) >= 4:
        result = find_place_fuzzy(country_code, town_n)
        if result:
            return True, result["name"], f"fuzzy:{result['name']}"

    return False, None, None


def _generate_variants(town: str) -> list:
    """
    Génère automatiquement des variantes pour
    couvrir le maximum de cas réels dans les messages SWIFT.
    """
    variants = []
    t = town

    # --- Translittérations arabes fréquentes ---
    replacements = [
        ("WED ", "OUED "),
        ("OUD ", "OUED "),
        ("OUAD ", "OUED "),
        ("EL ", "AL "),
        ("AL ", "EL "),
        ("BEN ", "BIN "),
        ("BIN ", "BEN "),
        ("BENI ", "BANI "),
        ("BANI ", "BENI "),
        ("OULD ", "OULED "),
        ("SIDI ", "SIDI "),
    ]
    for old, new in replacements:
        if t.startswith(old):
            variants.append(new + t[len(old):])
        t2 = t.replace(" " + old.strip(), " " + new.strip())
        if t2 != t:
            variants.append(t2)

    # --- Accents et caractères spéciaux ---
    # Version sans accents
    no_accent = _normalize(town)
    if no_accent != town:
        variants.append(no_accent)

    # --- Tirets vs espaces ---
    variants.append(t.replace("-", " "))
    variants.append(t.replace(" ", "-"))

    # --- Suffixes administratifs fréquents ---
    # Supprimer suffixes courants
    for suffix in [
        " VILLE", " CITY", " CENTRE", " CENTER",
        " NORD", " SUD", " EST", " OUEST",
        " NORTH", " SOUTH", " EAST", " WEST",
        " MEDINA", " CEDEX", " DISTRICT",
    ]:
        if t.endswith(suffix):
            variants.append(t[: -len(suffix)].strip())

    # --- Préfixes fréquents ---
    for prefix in ["SAINT ", "ST ", "SAINTE ", "STE ", "NEW ", "OLD "]:
        if t.startswith(prefix):
            variants.append(t[len(prefix):])

    # Dédoublonnage
    seen = set()
    result = []
    for v in variants:
        v = v.strip()
        if v and v != town and v not in seen:
            seen.add(v)
            result.append(v)

    return result