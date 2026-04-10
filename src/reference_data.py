"""reference_data.py — Chargement des référentiels JSON"""

import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent / "data" / "reference"


def _load_json(filename: str):
    path = BASE / filename
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


COUNTRY_NAME_TO_CODE = _load_json("country_aliases.json")
COUNTRY_CODES = set(COUNTRY_NAME_TO_CODE.values())

CAPITALS = _load_json("capitals.json")
ADDRESS_KEYWORDS = set(_load_json("address_keywords.json"))
ORG_HINTS = set(_load_json("org_hints.json"))
PARTY_ID_PREFIXES = set(_load_json("swift_party_id_codes.json").keys())
CITIES_BY_COUNTRY = _load_json("cities_by_country.json")
