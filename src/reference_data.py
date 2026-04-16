"""reference_data.py — Chargement des référentiels JSON
CORRECTION : ajout de CAPITALS dans les exports
"""

import json
import re
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "reference"


def _load_json(filename: str):
    path = BASE / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _normalize_country_alias(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = normalized.upper().strip()
    normalized = normalized.replace("&", " AND ")
    normalized = re.sub(r"[-,./()]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


SUPPLEMENTAL_COUNTRY_ALIASES = {
    "TURQUIE": "TR",
    "ALLEMAGNE": "DE",
    "ETATS UNIS": "US",
    "ETATS UNIS D AMERIQUE": "US",
    "ROYAUME UNI": "GB",
    "GRANDE BRETAGNE": "GB",
    "ESPAGNE": "ES",
    "ITALIE": "IT",
    "PORTUGAL": "PT",
    "SUISSE": "CH",
    "AUTRICHE": "AT",
    "PAYS BAS": "NL",
    "GRECE": "GR",
    "SUEDE": "SE",
    "NORVEGE": "NO",
    "DANEMARK": "DK",
    "FINLANDE": "FI",
    "IRLANDE": "IE",
    "ISLANDE": "IS",
    "POLOGNE": "PL",
    "HONGRIE": "HU",
    "ROUMANIE": "RO",
    "BULGARIE": "BG",
    "CROATIE": "HR",
    "SLOVAQUIE": "SK",
    "SLOVENIE": "SI",
    "SERBIE": "RS",
    "BOSNIE HERZEGOVINE": "BA",
    "MONTENEGRO": "ME",
    "MACEDOINE DU NORD": "MK",
    "TCHEQUIE": "CZ",
    "EMIRATS ARABES UNIS": "AE",
    "ARABIE SAOUDITE": "SA",
    "JORDANIE": "JO",
    "COREE DU SUD": "KR",
    "COREE DU NORD": "KP",
    "JAPON": "JP",
    "CHINE": "CN",
    "BELGIQUE": "BE",
    "LUXEMBOURG": "LU",
    "HOLLANDE": "NL",
    "MAROC": "MA",
    "ALGERIE": "DZ",
    "TUNISIE": "TN",
    "LIBYE": "LY",
    "EGYPTE": "EG",
    "SENEGAL": "SN",
    "COTE D IVOIRE": "CI",
    "CAMEROUN": "CM",
}


def _build_country_lookup() -> dict:
    lookup = {}
    for raw_name, code in _load_json("country_aliases.json").items():
        lookup[_normalize_country_alias(raw_name)] = code
    for raw_name, code in SUPPLEMENTAL_COUNTRY_ALIASES.items():
        lookup[_normalize_country_alias(raw_name)] = code
    return lookup


COUNTRY_NAME_TO_CODE = _build_country_lookup()
COUNTRY_CODES = set(COUNTRY_NAME_TO_CODE.values())


def resolve_country_code(value: str) -> str:
    """Résout un nom de pays ou code ISO vers le code ISO 2 lettres."""
    if not value:
        return None
    v = value.strip().upper()
    # Code ISO direct
    if v in COUNTRY_CODES:
        return v
    # Alias normalisé
    return COUNTRY_NAME_TO_CODE.get(_normalize_country_alias(value))


# ✅ CORRECTION : CAPITALS exporté pour le fallback capitale dans e1_parser
CAPITALS = _load_json("capitals.json")
ADDRESS_KEYWORDS = set(_load_json("address_keywords.json"))
ORG_HINTS = set(_load_json("org_hints.json"))
PARTY_ID_PREFIXES = set(_load_json("swift_party_id_codes.json").keys())
CITIES_BY_COUNTRY = _load_json("cities_by_country.json")