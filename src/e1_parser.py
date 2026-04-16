"""e1_parser.py — Étape E1: Parsing structuré et libre des champs SWIFT
CORRECTIONS GLOBALES :
- Intégration GeoNames pour extraire les villes masquées dans les adresses (ex: ZONE INDUSTRIELLE ENFIDHA)
- Nettoyage des espaces parasites dans SHORT_COUNTRY_TO_ISO
- Fallback robuste sur GeoNames avant la capitale
"""
import re
from typing import List, Optional, Tuple
from src.models import (
    CanonicalParty, CanonicalMeta, CountryTown, DateOfBirth, PlaceOfBirth,
    PartyIdentifier, PreprocessResult,
)
from src.reference_data import (
    COUNTRY_NAME_TO_CODE, COUNTRY_CODES, ADDRESS_KEYWORDS, ORG_HINTS,
    PARTY_ID_PREFIXES, CITIES_BY_COUNTRY, CAPITALS, resolve_country_code,
)
from src.ambiguity_resolver import resolve_city_country_ambiguity
from src.toponym_normalizer import town_known_for_country

# ✅ Import GeoNames Validator avec gestion d'erreur si DB non dispo
try:
    from src.geonames.geonames_validator import validate_town_in_country
    GEONAMES_AVAILABLE = True
except ImportError:
    GEONAMES_AVAILABLE = False

SHORT_COUNTRY_TO_ISO = {
    "A": "AT", "B": "BE", "D": "DE", "E": "ES", "F": "FR",
    "G": "GR", "I": "IT", "L": "LU", "N": "NO", "P": "PT",
    "S": "SE", "V": "VA",
}

def _norm(value):
    if not value: return ""
    return re.sub(r"\s+", " ", value.strip())

def _empty(field_type, role, message_id, raw=None):
    return CanonicalParty(
        message_id=message_id, field_type=field_type, role=role, raw=raw,
        meta=CanonicalMeta(source_format=field_type, parse_confidence=0.0),
    )

def _all_known_cities_upper():
    result = set()
    for _, cities in CITIES_BY_COUNTRY.items():
        for city in cities: result.add(_norm(city).upper())
    return result

KNOWN_CITIES = _all_known_cities_upper()

def _is_known_country_name(line): return resolve_country_code(line) is not None
def _is_known_city(line): return _norm(line).upper() in KNOWN_CITIES
def _contains_address_keyword(value):
    up = _norm(value).upper()
    if not up: return False
    for keyword in ADDRESS_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", up): return True
    return False
def _is_address(line):
    up = _norm(line).upper()
    if _contains_address_keyword(up): return True
    if re.search(r"\d", up): return True
    return False
def _looks_like_real_address_fragment(value):
    up = _norm(value).upper()
    return bool(up) and _contains_address_keyword(up)

def _clean_town_value(town):
    """Nettoie les suffixes parasites SANS couper les noms de villes légitimes."""
    if not town: return town
    cleaned = _norm(town)
    ARTIFACTS = {"->", "→", "??", "N/A", "NA", "NONE", "NULL", "-", "..."}
    if cleaned.upper() in ARTIFACTS: return None
    if re.fullmatch(r"\d{3,8}", cleaned): return None
    
    # ✅ CORRECTION CRITIQUE : Vérifier que les 2 derniers caractères sont bien un code pays ISO
    m = re.match(r'^(.+?)\s*[-/\s]\s*([A-Z]{2})\s*$', cleaned, flags=re.IGNORECASE)
    if m and m.group(2).upper() in COUNTRY_CODES:
        cleaned = m.group(1).strip()
    else:
        # Fallback simple : espace + code pays
        m2 = re.match(r'^(.+?)\s+([A-Z]{2})\s*$', cleaned)
        if m2 and m2.group(2).upper() in COUNTRY_CODES:
            cleaned = m2.group(1).strip()
            
    # Supprimer nom de pays connu en fin (ex: "TUNIS TUNISIE" -> "TUNIS")
    up = cleaned.upper()
    for cname in sorted(COUNTRY_NAME_TO_CODE.keys(), key=len, reverse=True):
        suffix = " " + cname
        if up.endswith(suffix) and len(cleaned) > len(suffix):
            cleaned = cleaned[:-len(suffix)].strip()
            break
            
    return cleaned or None

def _detect_org(name_lines):
    txt = " ".join(name_lines).upper()
    if any(k in txt for k in ORG_HINTS): return True
    words = txt.split()
    if len(words) == 2 and all(re.fullmatch(r"[A-Z.-]+", w) for w in words): return False
    return None

def _deduplicate_addresses(address_lines):
    result = []
    for line in address_lines:
        line = _norm(line)
        if not line: continue
        skip = False
        to_remove = []
        for existing in result:
            ex_n = _norm(existing).upper()
            cur_n = line.upper()
            if cur_n == ex_n or ex_n in cur_n:
                skip = True; break
            if cur_n in ex_n: to_remove.append(existing)
        if skip: continue
        for item in to_remove:
            if item in result: result.remove(item)
        result.append(line)
    return result

def _is_postal_town_line(line, geo):
    if not geo: return False
    line_n = _norm(line).upper()
    if geo.postal_code and geo.town:
        if line_n == f"{geo.postal_code} {_norm(geo.town).upper()}": return True
    if geo.town and line_n == _norm(geo.town).upper(): return True
    if geo.postal_code and line_n == geo.postal_code: return True
    return False

def _parse_party_identifier(raw):
    parts = [p.strip() for p in raw.split("/") if p.strip()]
    code = parts[0].upper() if parts else None
    country = parts[1].upper() if len(parts) >= 2 else None
    issuer = identifier = None
    if code in {"NIDN", "CCPT", "ARNU", "SOSE", "TXID"}:
        identifier = parts[2] if len(parts) >= 3 else None
    elif code in {"CUST", "DRLC", "EMPL"}:
        issuer = parts[2] if len(parts) >= 3 else None
        identifier = parts[3] if len(parts) >= 4 else None
    elif len(parts) >= 3: identifier = parts[-1]
    return PartyIdentifier(code=code, country=country, issuer=issuer, identifier=identifier)

def _split_embedded_country_prefix(line):
    raw = _norm(line)
    up = raw.upper()
    if len(up) < 4: return None, raw
    prefix = up[:2]
    if prefix not in COUNTRY_CODES: return None, raw
    PROTECTED = (
        "PAR", "PAL", "PAD", "PAN", "PAM", "MAD", "MAR", "MAN", "MAL", "MAP",
        "BER", "BEL", "BEN", "BRU", "BEI", "IST", "IND", "IRE", "NOR",
        "LIM", "LIS", "LIL", "TOK", "TOR", "TOU", "SIN", "SIG",
        "LAG", "LAH", "LAU", "NAI", "NAP", "NAN", "GEN", "GEO",
        "BRE", "BRM", "RIG", "RIC", "RIM", "LUX", "AMS", "ANK", "ANT",
        "BAR", "BAG", "BAK", "BOR", "BOL", "BOG", "BRA", "BUD", "BUE",
        "CAI", "CAP", "CAS", "COP", "COL", "DAK", "DAM", "DAR", "DUB", "DUS",
        "EDI", "FRA", "FRE", "GLA", "HAM", "HAN", "HAV", "HEL", "ISL",
        "JAK", "KAB", "KAM", "KAR", "KIG", "KIN", "KUA", "KUW",
        "LON", "LOM", "LUS", "LYO", "MEX", "MEL", "MIA", "MIL", "MIN",
        "MOS", "MON", "MUN", "MUM", "MUS", "NIA", "NIC", "OSL", "OTT",
        "OUA", "PHN", "PHO", "POR", "POD", "PRA", "PRE", "QUI", "REY",
        "ROM", "ROT", "SAN", "SEO", "SEV", "SKO", "SOF", "STO", "SYD",
        "TAI", "TAS", "TAL", "TEH", "THE", "TIR", "TUN", "ULA", "VAL", "VAN",
        "VIE", "VIL", "WAR", "WAS", "YAO", "YER", "ZAG",
    )
    if up.startswith(PROTECTED) or up in KNOWN_CITIES: return None, raw
    rest = raw[2:].strip(" ,-/")
    if not rest or len(rest) < 2: return None, raw
    return prefix, rest

def _split_inline_name_address(line):
    raw = _norm(line)
    up = raw.upper()
    match = re.search(
        r"\b(RUE|AVENUE|AVE|STREET|ROAD|ROUTE|STRASSE|BOULEVARD|BD|ZONE|"
        r"CITE|IMMEUBLE|IMM|APT|APPT|LANE|DRIVE|WAY)\b", up,
    )
    if not match: return raw, None
    idx = match.start()
    left = raw[:idx].strip(" ,-/")
    right = raw[idx:].strip(" ,-/")
    if not left or not right: return raw, None
    return left, _norm(right)

def _looks_like_org_continuation(line):
    up = _norm(line).upper()
    if _is_known_city(up) or _is_known_country_name(up) or _is_address(up): return False
    words = up.split()
    if not words: return False
    if len(words) <= 3 and any(w in ORG_HINTS for w in words): return True
    if len(words) <= 3 and all(re.fullmatch(r"[A-Z.&-]+", w) for w in words): return True
    return False

def _parse_structured_country_town(value):
    raw = _norm(value)
    parts = [p.strip() for p in raw.split("/")]
    if len(parts) == 1: return None, False
    country = parts[0].upper()
    rest = parts[1]
    if country not in COUNTRY_CODES: return None, False
    postal_code = None
    town = rest
    m = re.match(r"^(.*?)(?:\s+([0-9A-Z-]{3,10}))$", rest)
    if m and re.search(r"\d", m.group(2)):
        town = m.group(1).strip(",")
        postal_code = m.group(2).strip()
    town = _clean_town_value(town)
    return CountryTown(country=country, town=town or None, postal_code=postal_code), True

def _parse_place_of_birth(value):
    raw = _norm(value)
    parts = [p.strip() for p in raw.split("/")]
    if len(parts) >= 2: return PlaceOfBirth(country=parts[0].upper(), city=parts[1])
    return PlaceOfBirth(country=None, city=raw or None)

def _parse_date_of_birth(value):
    raw = _norm(value)
    if re.fullmatch(r"\d{8}", raw):
        return DateOfBirth(raw=raw, year=raw[:4], month=raw[4:6], day=raw[6:8])
    return DateOfBirth(raw=raw)

def _parse_country_encoded_line(line):
    raw = _norm(line)
    if "/" not in raw: return None
    left, right = [p.strip() for p in raw.split("/", 1)]
    if not left or not right: return None
    cc = left.upper()
    if cc not in COUNTRY_CODES: return None
    encoded = resolve_country_code(right)
    if encoded == cc: return CountryTown(country=cc, town=None, postal_code=None)
    return CountryTown(country=cc, town=right, postal_code=None)

def _extract_country_postal_town_fragment(line):
    """Détecte fragments géo dans une ligne."""
    raw = _norm(line)
    for pat in [
        r"\b([A-Z]{2})/(\d{3,10})\s+([A-Z][A-Z0-9()' .\-]+)$",
        r"\b([A-Z]{2})\s+(\d{3,10})\s+([A-Z][A-Z0-9()' .\-]+)$",
    ]:
        m = re.search(pat, raw, flags=re.IGNORECASE)
        if m:
            cc = m.group(1).upper()
            if cc in COUNTRY_CODES:
                town = _clean_town_value(_norm(m.group(3)))
                if town: return m.start(), m.end(), CountryTown(country=cc, town=town, postal_code=m.group(2))

    m = re.search(r"^([A-Za-z]{1,2})\s*[-–]\s*(\d{3,10})\s+([A-Z][A-Z0-9()' .\-]+)$", raw, flags=re.IGNORECASE)
    if m:
        cc = m.group(1).upper().strip()
        if len(cc) == 1: cc = SHORT_COUNTRY_TO_ISO.get(cc, cc)
        if cc in COUNTRY_CODES:
            town = _clean_town_value(_norm(m.group(3)))
            if town: return m.start(), m.end(), CountryTown(country=cc, town=town, postal_code=m.group(2))

    m = re.match(r"^(\d{4,6})\s+([A-Z][A-Z0-9()' .\-]+)$", raw, flags=re.IGNORECASE)
    if m:
        town = _clean_town_value(_norm(m.group(2)))
        if town: return 0, len(raw), CountryTown(country=None, town=town, postal_code=m.group(1))

    return None

def _apply_iban_and_capital_fallback(geo, iban_country, warnings):
    """IBAN prime pour pays + fallback capitale si ville manque."""
    if geo.town: geo.town = _clean_town_value(geo.town)
    if iban_country:
        if not geo.country:
            geo.country = iban_country
            warnings.append("country_from_iban")
        elif geo.country != iban_country:
            warnings.append(f"country_conflict_iban_hint_only:{iban_country}!=explicit:{geo.country}")
    if geo.country and not geo.town:
        capital = CAPITALS.get(geo.country)
        if capital:
            geo.town = capital
            warnings.append(f"town_inferred_from_capital:{geo.country}→{capital}")
    return geo

def _extract_geo_from_free_lines(lines, warnings):
    if not lines: return CountryTown(), 0
    last = _norm(lines[-1])
    up = last.upper()

    encoded = _parse_country_encoded_line(last)
    if encoded:
        if encoded.town is None: return encoded, 1
        if _is_known_country_name(encoded.town):
            return CountryTown(country=encoded.country, town=None, postal_code=None), 1

    if _is_known_city(last): return CountryTown(country=None, town=last, postal_code=None), 1

    frag = _extract_country_postal_town_fragment(last)
    if frag:
        _, _, ct = frag
        if ct.country or ct.postal_code: return ct, 1

    m_short = re.match(r"^([A-Za-z]{1,2})\s*[-–]?\s*(\d{4,6})\s+(.+)$", last, flags=re.IGNORECASE)
    if m_short:
        cc = m_short.group(1).upper().strip()
        if len(cc) == 1: cc = SHORT_COUNTRY_TO_ISO.get(cc, cc)
        if cc in COUNTRY_CODES:
            town = _clean_town_value(_norm(m_short.group(3)))
            if town:
                warnings.append(f"short_country_code_normalized:{m_short.group(1).upper()}→{cc}")
                return CountryTown(country=cc, town=town, postal_code=m_short.group(2)), 1

    code = resolve_country_code(last)
    if code:
        if len(lines) >= 2:
            prev = _norm(lines[-2])
            frag_prev = _extract_country_postal_town_fragment(prev)
            if frag_prev:
                _, _, ct_prev = frag_prev
                if ct_prev.country == code or ct_prev.country is None: ct_prev.country = code
                ct_prev.town = _clean_town_value(ct_prev.town)
                return ct_prev, 2
            m = re.match(r"^(\d{4,6})\s+(.+)$", prev)
            if m:
                town = _clean_town_value(m.group(2).strip())
                return CountryTown(country=code, town=town, postal_code=m.group(1).strip()), 2
            
            # ==============================================================================
            # ✅ CORRECTION CRITIQUE : Gestion des villes masquées dans l'adresse via GeoNames
            # Cas : "ZONE INDUSTRIELLE ENFIDHA" -> On vérifie si "ENFIDHA" est une ville TN
            # ==============================================================================
            if _is_address(prev):
                words = prev.split()
                if words:
                    candidate = words[-1] # Prend le dernier mot (ex: ENFIDHA)
                    
                    # 1. Vérification rapide via GeoNames (Source de vérité mondiale)
                    if GEONAMES_AVAILABLE:
                        is_valid, canonical, _ = validate_town_in_country(code, candidate)
                        if is_valid:
                            warnings.append(f"town_extracted_via_geonames_from_address:{candidate}→{canonical}")
                            return CountryTown(country=code, town=canonical, postal_code=None), 1
                    
                    # 2. Fallback JSON local si GeoNames indisponible ou échec
                    if town_known_for_country(code, candidate):
                        warnings.append(f"town_found_in_json_from_address:{candidate}")
                        return CountryTown(country=code, town=candidate, postal_code=None), 1
            # ==============================================================================

            if prev and (not _is_address(prev)):
                return CountryTown(country=code, town=_clean_town_value(prev), postal_code=None), 2
        
        return CountryTown(country=code, town=None, postal_code=None), 1

    for name, code in COUNTRY_NAME_TO_CODE.items():
        suffix = " " + name
        if up.endswith(suffix):
            town = _clean_town_value(last[:-len(suffix)].strip())
            return CountryTown(country=code, town=town or None, postal_code=None), 1 

    embedded_country, cleaned_town = _split_embedded_country_prefix(last)
    if embedded_country and cleaned_town:
        cleaned_cc = resolve_country_code(cleaned_town)
        if cleaned_cc == embedded_country:
            return CountryTown(country=embedded_country, town=None, postal_code=None), 1
        warnings.append(f"country_embedded_in_town_line:{embedded_country}")
        town = _clean_town_value(cleaned_town)
        return CountryTown(country=embedded_country, town=town, postal_code=None), 1

    m = re.match(r"^(\d{4,6})\s+(.+)$", last)
    if m:
        town = _clean_town_value(m.group(2).strip())
        return CountryTown(country=None, town=town, postal_code=m.group(1).strip()), 1

    return CountryTown(country=None, town=_clean_town_value(last), postal_code=None), 1

def parse_free_party_field(pre, field_type, role, message_id):
    res = _empty(field_type, role, message_id, raw=pre.normalized_text or pre.raw_input)
    warnings = res.meta.warnings
    lines = pre.lines[:]
    idx = 0
    iban_country = pre.meta.iban_country
    if lines and lines[0].startswith("/"):
        res.account = lines[0]
        idx = 1

    content = [_norm(x) for x in lines[idx:] if _norm(x)]
    if not content:
        warnings.append("no_content_after_account")
        res.meta.parse_confidence = 0.0
        return res

    # CAS SPÉCIAL 1 : une seule ligne qui finit par un pays
    if len(content) == 1:
        only_line = content[0]
        up = only_line.upper()
        for country_name, country_code in COUNTRY_NAME_TO_CODE.items():
            suffix = " " + country_name
            if up.endswith(suffix):
                left = only_line[:-len(suffix)].strip()
                if left:
                    res.name = [left]
                    res.country_town = _apply_iban_and_capital_fallback(
                        CountryTown(country=country_code, town=None, postal_code=None),
                        iban_country, warnings
                    )
                    warnings.append("town_missing_from_name_country_pattern")
                    res.is_org = _detect_org(res.name)
                    res.meta.parse_confidence = 0.85
                    return res

    geo, consumed = _extract_geo_from_free_lines(content, warnings)

    if consumed > 0 and content:
        last_line = _norm(content[-1])
        frag = _extract_country_postal_town_fragment(last_line)
        pure_geo_line = False
        if frag:
            start_idx, end_idx, _ = frag
            frag_text = _norm(last_line[start_idx:end_idx])
            if frag_text.upper() == last_line.upper(): pure_geo_line = True
        else:
            if not _is_address(last_line): pure_geo_line = True
        if pure_geo_line: content = content[:-consumed]

    geo = _apply_iban_and_capital_fallback(geo, iban_country, warnings)
    if not content:
        res.country_town = geo
        res.address_lines = _deduplicate_addresses(res.address_lines)
        res.is_org = _detect_org(res.name)
        res.meta.parse_confidence = 0.80
        return res

    # NOM
    first = content[0]
    split_name, split_addr = _split_inline_name_address(first)
    if split_addr:
        res.name = [split_name]
        res.address_lines.append(split_addr)
        warnings.append("name_address_mixed")
    else:
        res.name = [first]

    remaining = content[1:]
    if remaining:
        candidate = _norm(remaining[0])
        looks_geo = (
            _is_known_city(candidate)
            or _is_known_country_name(candidate)
            or any(candidate.upper().endswith(" " + cn) for cn in COUNTRY_NAME_TO_CODE)
        )
        if not looks_geo and _looks_like_org_continuation(candidate):
            res.name[0] = f"{res.name[0]} {candidate}".strip()
            remaining = remaining[1:]
            warnings.append("multiline_name_fused:1")

    # CAS SPÉCIAL 2 : [ligne candidate] + [pays]
    if len(remaining) == 2:
        line1 = _norm(remaining[0])
        line2 = _norm(remaining[1]).upper()
        line2_country = resolve_country_code(line2)
        if line2_country:
            m = re.match(r"^(\d{4,6})\s+(.+)$", line1)
            if m:
                town = _clean_town_value(m.group(2).strip())
                res.country_town = _apply_iban_and_capital_fallback(
                    CountryTown(country=line2_country, town=town, postal_code=m.group(1).strip()),
                    iban_country, warnings
                )
                res.address_lines = _deduplicate_addresses(res.address_lines)
                res.is_org = _detect_org(res.name)
                res.meta.parse_confidence = 0.88
                return res

            decision = resolve_city_country_ambiguity(line1, line2)
            if decision.label == "TOWN":
                res.country_town = _apply_iban_and_capital_fallback(
                    CountryTown(country=line2_country, town=line1, postal_code=None),
                    iban_country, warnings
                )
                res.address_lines = _deduplicate_addresses(res.address_lines)
                warnings.append(f"ambiguous_city_country_tail_resolved_as_town:{decision.reason}")
                res.is_org = _detect_org(res.name)
                res.meta.parse_confidence = decision.confidence
                return res
            if decision.label == "ADDRESS":
                res.address_lines.append(line1)
                res.country_town = _apply_iban_and_capital_fallback(
                    CountryTown(country=line2_country, town=None, postal_code=None),
                    iban_country, warnings
                )
                res.address_lines = _deduplicate_addresses(res.address_lines)
                warnings.append(f"ambiguous_city_country_tail_resolved_as_address:{decision.reason}")
                res.is_org = _detect_org(res.name)
                res.meta.parse_confidence = decision.confidence
                return res
            res.country_town = _apply_iban_and_capital_fallback(
                CountryTown(country=line2_country, town=line1, postal_code=None),
                iban_country, warnings
            )
            res.address_lines = _deduplicate_addresses(res.address_lines)
            warnings.append("ambiguous_city_country_tail")
            res.is_org = _detect_org(res.name)
            res.meta.parse_confidence = 0.65
            return res

    # Lignes restantes
    for line in remaining:
        line = _norm(line)
        if _is_postal_town_line(line, geo): continue
        frag = _extract_country_postal_town_fragment(line)
        if frag:
            start_idx, _, ct = frag
            if not geo.country: geo.country = ct.country
            if not geo.town: geo.town = _clean_town_value(ct.town)
            if not geo.postal_code: geo.postal_code = ct.postal_code
            addr_part = _norm(line[:start_idx]).strip(" ,-/")
            if addr_part: res.address_lines.append(addr_part)
            continue
        if geo.town and _norm(line).upper() == _norm(geo.town).upper(): continue
        line_country = resolve_country_code(line)
        if line_country:
            if not geo.country: geo.country = line_country
            continue
        res.address_lines.append(line) 
        if not _is_address(line):
            warnings.append(f"unclassified_line_to_address:{line}")

    if geo.town and _looks_like_real_address_fragment(geo.town):
        if geo.town not in res.address_lines: res.address_lines.insert(0, geo.town)
        geo.town = None
        warnings.append("town_reclassified_as_address")

    geo = _apply_iban_and_capital_fallback(geo, iban_country, warnings)
    res.address_lines = _deduplicate_addresses(res.address_lines)
    res.country_town = geo
    res.is_org = _detect_org(res.name)

    confidence = 0.90
    if "name_address_mixed" in warnings: confidence -= 0.05
    if any(w.startswith("multiline_name_fused") for w in warnings): confidence -= 0.05
    if "town_reclassified_as_address" in warnings: confidence -= 0.10
    if any(w.startswith("town_inferred_from_capital") for w in warnings): confidence -= 0.05
    if any(w.startswith("unclassified_line_to_address:") for w in warnings): confidence -= 0.05
    if "town_missing_from_name_country_pattern" in warnings: confidence -= 0.05
    if "ambiguous_city_country_tail" in warnings: confidence -= 0.10

    res.meta.parse_confidence = max(0.0, round(confidence, 2))
    return res

def parse_structured_50F(pre, message_id="MSG"):
    res = _empty("50F", "debtor", message_id, raw=pre.normalized_text or pre.raw_input)
    warnings = res.meta.warnings
    lines = pre.lines[:]
    idx = 0
    if lines and lines[0].startswith("/"):
        res.account = lines[0]
        idx = 1
    if idx < len(lines):
        first_non_account = lines[idx]
        prefix = first_non_account.split("/", 1)[0].upper() if "/" in first_non_account else ""
        if prefix in PARTY_ID_PREFIXES:
            res.party_id = _parse_party_identifier(first_non_account)
            idx += 1
    has_4 = has_5 = seen_3 = False
    for line in lines[idx:]:
        if "/" not in line: continue
        tag, value = line.split("/", 1)
        tag = tag.strip()
        value = _norm(value)
        if tag == "1": res.name.append(value)
        elif tag == "2": res.address_lines.append(value)
        elif tag == "3":
            parsed_ct, ok = _parse_structured_country_town(value)
            if ok and parsed_ct: res.country_town = parsed_ct; seen_3 = True
            else:
                res.country_town = CountryTown(country=None, town=value, postal_code=None)
                warnings.append("invalid_structured_line_3")
        elif tag == "4": res.dob = _parse_date_of_birth(value); has_4 = True
        elif tag == "5": res.pob = _parse_place_of_birth(value); has_5 = True
        elif tag == "6":
            parts = [p.strip() for p in value.split("/")]
            if len(parts) >= 3: res.org_id = PartyIdentifier(code="CUST", country=parts[0].upper(), issuer=parts[1], identifier=parts[2])
        elif tag == "7":
            parts = [p.strip() for p in value.split("/")]
            res.national_id = parts[1] if len(parts) >= 2 else value
        elif tag == "8": res.postal_complement = value
    if not seen_3 and "invalid_structured_line_3" not in warnings: warnings.append("missing_mandatory_3")
    if has_4 != has_5: warnings.append("4_and_5_must_appear_together")
    if res.country_town: res.country_town = _apply_iban_and_capital_fallback(res.country_town, pre.meta.iban_country, warnings)
    res.is_org = _detect_org(res.name)
    confidence = 1.0
    if "missing_mandatory_3" in warnings: confidence -= 0.30
    if "invalid_structured_line_3" in warnings: confidence -= 0.25
    if "4_and_5_must_appear_together" in warnings: confidence -= 0.20
    res.meta.parse_confidence = max(0.0, round(confidence, 2))
    return res

def parse_structured_59F(pre, message_id="MSG"):
    res = _empty("59F", "creditor", message_id, raw=pre.normalized_text or pre.raw_input)
    warnings = res.meta.warnings
    lines = pre.lines[:]
    idx = 0
    if lines and lines[0].startswith("/"):
        res.account = lines[0]
        idx = 1
    seen_3 = False
    for line in lines[idx:]:
        if "/" not in line: continue
        tag, value = line.split("/", 1)
        tag = tag.strip()
        value = _norm(value)
        if tag == "1": res.name.append(value)
        elif tag == "2": res.address_lines.append(value)
        elif tag == "3":
            parsed_ct, ok = _parse_structured_country_town(value)
            if ok and parsed_ct: res.country_town = parsed_ct; seen_3 = True
            else:
                if value.upper() in COUNTRY_CODES:
                    res.country_town = CountryTown(country=value.upper(), town=None, postal_code=None)
                    seen_3 = True
                else: warnings.append("invalid_structured_line_3")
    if not seen_3 and "invalid_structured_line_3" not in warnings: warnings.append("missing_mandatory_3")
    if res.country_town: res.country_town = _apply_iban_and_capital_fallback(res.country_town, pre.meta.iban_country, warnings)
    res.is_org = _detect_org(res.name)
    confidence = 1.0
    if "missing_mandatory_3" in warnings: confidence -= 0.30
    if "invalid_structured_line_3" in warnings: confidence -= 0.25
    res.meta.parse_confidence = max(0.0, round(confidence, 2))
    return res

def parse_field(pre, message_id="MSG"):
    t = (pre.meta.detected_field_type or "").upper()
    if t == "50K": return parse_free_party_field(pre, "50K", "debtor", message_id)
    if t == "59": return parse_free_party_field(pre, "59", "creditor", message_id)
    if t == "50F": return parse_structured_50F(pre, message_id)
    if t == "59F": return parse_structured_59F(pre, message_id)
    raise Exception(f"Type non supporté:{t}")