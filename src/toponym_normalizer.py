"""toponym_normalizer.py — Normalisation et comparaison de toponymes"""

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Tuple

from src.reference_data import CITIES_BY_COUNTRY


TOPONYM_VARIANTS: Dict[str, str] = {
    "WED RMAL": "OUED REMEL",
    "OUED RMAL": "OUED REMEL",
    "WED REMEL": "OUED REMEL",
    "OUED REMEL": "OUED REMEL",
    "OUED RMEL": "OUED REMEL",
    "WED RMEL": "OUED REMEL",
    "EL OMRANE": "OMRANE(EL)",
    "EL OMRANE SUPERIEUR": "OMRANE SUPERIEUR",
    "EL MANAR": "MANAR(EL)",
    "ARIANA VILLE": "ARIANA",
    "ARIANA SUPERIEUR": "ARIANA",
    "BIZERTA": "BIZERTE",
    "GABES SUD": "GABES",
    "TUNIS BELVEDERE": "TUNIS",
    "SFAX VILLE": "SFAX",
    "SFAX MEDINA": "SFAX",
    "DAOUR HICHER": "DAOUR HICHER",
    "TNDAOUR HICHER": "DAOUR HICHER",
}

ADDRESS_NOISE_WORDS = {
    "BP", "B.P", "B.P.", "BOX", "PO", "P.O", "P.O.", "POSTE", "POSTAL",
    "N", "NO", "NUM", "NUMERO",
}


def _strip_accents(value: str) -> str:
    value = unicodedata.normalize("NFD", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return unicodedata.normalize("NFC", value)


def _basic_normalize(value: Optional[str]) -> str:
    if not value:
        return ""
    value = _strip_accents(value.upper())
    for ch in "-_/\\(),.":
        value = value.replace(ch, " ")
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _phonetic_normalize(value: str) -> str:
    s = _basic_normalize(value)
    s = re.sub(r"\bWED\b", "OUED", s)
    s = re.sub(r"\bOUD\b", "OUED", s)
    s = re.sub(r"\bOUAD\b", "OUED", s)
    s = re.sub(r"\bAL\b", "EL", s)
    s = re.sub(r"\bBEN\b", "BIN", s)
    tokens = []
    for tok in s.split():
        t = tok.replace("AA", "A").replace("EE", "E").replace("II", "I").replace("OO", "O").replace("UU", "U")
        if len(t) > 3:
            first = t[0]
            rest = re.sub(r"[AEIOU]", "", t[1:])
            t = first + rest
        tokens.append(t)
    return re.sub(r"\s+", " ", " ".join(tokens)).strip()


def canonicalize_toponym(value: Optional[str]) -> str:
    if not value:
        return ""
    raw = _basic_normalize(value)
    if raw in TOPONYM_VARIANTS:
        return TOPONYM_VARIANTS[raw]
    ph = _phonetic_normalize(raw)
    for observed, canonical in TOPONYM_VARIANTS.items():
        if _phonetic_normalize(observed) == ph:
            return canonical
    return raw


def comparable_toponym(value: Optional[str]) -> str:
    if not value:
        return ""
    canonical = canonicalize_toponym(value)
    comp = _phonetic_normalize(canonical)
    comp = comp.replace(" ", "")
    return comp


def toponyms_equivalent(a: Optional[str], b: Optional[str], threshold: float = 0.84) -> bool:
    ca = comparable_toponym(a)
    cb = comparable_toponym(b)
    if not ca or not cb:
        return False
    if ca == cb:
        return True
    ratio = SequenceMatcher(None, ca, cb).ratio()
    return ratio >= threshold


def extract_toponym_candidates_from_address(address_line: Optional[str]) -> List[str]:
    if not address_line:
        return []
    raw = _basic_normalize(address_line)
    tokens = raw.split()
    filtered = [tok for tok in tokens if tok not in ADDRESS_NOISE_WORDS and not re.fullmatch(r"\d+", tok)]
    if not filtered:
        return []
    candidates = [" ".join(filtered)]
    n = len(filtered)
    for size in range(1, min(4, n) + 1):
        for i in range(n - size + 1):
            candidates.append(" ".join(filtered[i:i + size]))
    deduped, seen = [], set()
    for c in candidates:
        c2 = _basic_normalize(c)
        if c2 and c2 not in seen:
            seen.add(c2)
            deduped.append(c2)
    return deduped


def build_country_toponym_index() -> Dict[str, List[str]]:
    result: Dict[str, List[str]] = {}
    for country, cities in CITIES_BY_COUNTRY.items():
        result[country] = []
        seen = set()
        for city in cities:
            canon = canonicalize_toponym(city)
            if canon not in seen:
                seen.add(canon)
                result[country].append(canon)
    return result


COUNTRY_TOPONYM_INDEX = build_country_toponym_index()


def town_known_for_country(country: Optional[str], town: Optional[str]) -> bool:
    if not country or not town:
        return False
    country = _basic_normalize(country)
    if country not in COUNTRY_TOPONYM_INDEX:
        return False
    for known in COUNTRY_TOPONYM_INDEX[country]:
        if toponyms_equivalent(town, known):
            return True
    return False


def reduce_to_known_core_toponym(
    country: Optional[str],
    town: Optional[str],
) -> Optional[str]:
    """
    Réduit un toponyme composé vers une ville coeur connue pour le pays.
    Exemples:
    - "TUNIS BELVEDERE" -> "TUNIS"
    - "PARIS CENTRE" -> "PARIS"

    La réduction reste conservative:
    - on ne travaille que dans le pays fourni
    - on cherche d'abord les sous-toponymes les plus longs
    - on ne retourne qu'une ville déjà connue dans nos référentiels
    """
    if not country or not town:
        return None

    country_n = _basic_normalize(country)
    town_n = _basic_normalize(town)
    if not town_n or country_n not in COUNTRY_TOPONYM_INDEX:
        return None

    known_cities = COUNTRY_TOPONYM_INDEX[country_n]

    # Si déjà connu, on renvoie la forme canonique correspondante.
    for known in known_cities:
        if toponyms_equivalent(town_n, known):
            return known

    tokens = town_n.split()
    if len(tokens) < 2:
        return None

    candidates = []

    # Sous-chaînes contiguës, en privilégiant les plus longues.
    for size in range(len(tokens) - 1, 0, -1):
        for start in range(0, len(tokens) - size + 1):
            candidates.append(" ".join(tokens[start:start + size]))

    seen = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        for known in known_cities:
            if toponyms_equivalent(candidate, known):
                return known

    return None


def find_variant_match_in_address(address_lines: List[str], town: Optional[str]) -> Optional[Tuple[str, str]]:
    if not town:
        return None
    canonical_town = canonicalize_toponym(town)
    for line in address_lines or []:
        candidates = extract_toponym_candidates_from_address(line)
        for candidate in candidates:
            if toponyms_equivalent(candidate, canonical_town):
                return candidate, canonical_town
    return None
