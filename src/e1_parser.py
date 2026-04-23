"""e1_parser.py — Étape E1 : Parsing structuré et libre des champs SWIFT
CORRECTIONS CRITIQUES :
- Ajout regex pour format "PAYS VILLE POSTAL" (ex: TN ELHAOUARIA 8045)
- Suppression des espaces parasites dans SHORT_COUNTRY_TO_ISO et ARTIFACTS
- Nettoyage robuste des villes
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

# ✅ FIX: Suppression des espaces parasites dans les clés/valeurs
SHORT_COUNTRY_TO_ISO = {
    "A": "AT", "B": "BE", "D": "DE", "E": "ES", "F": "FR",
    "G": "GR", "I": "IT", "L": "LU", "N": "NO", "P": "PT",
    "S": "SE", "V": "VA",
}

def _norm(value):
    """Normalise: majuscules, espaces uniques, strip."""
    if not value: return ""
    return " ".join(value.strip().upper().split())

def _empty(field_type, role, message_id, raw=None):
    return CanonicalParty(
        message_id=message_id, field_type=field_type, role=role, raw=raw,
        meta=CanonicalMeta(source_format=field_type, parse_confidence=0.0),
    )

def _all_known_cities_upper():
    result = {}
    for country, cities in CITIES_BY_COUNTRY.items():
        for city in cities: result[_norm(city).upper()] = country
    return result

KNOWN_CITIES = _all_known_cities_upper()

from src.toponym_normalizer import canonicalize_toponym
def _is_known_country_name(line): return resolve_country_code(line) is not None
def _is_known_city(line): return canonicalize_toponym(_norm(line).upper()) in KNOWN_CITIES
def _known_city_country(line): return KNOWN_CITIES.get(canonicalize_toponym(_norm(line).upper()))
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

def _extract_town_from_zone_line(line: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Détecte et extrait la ville d'une ligne comme "ZONE INDUSTRIELLE ENFIDHA".
    Retourne (address_part, town_candidate).
    
    Exemples:
    - "ZONE INDUSTRIELLE ENFIDHA" → ("ZONE INDUSTRIELLE", "ENFIDHA")
    - "PARC COMMERCIAL SOUSSE" → ("PARC COMMERCIAL", "SOUSSE")
    - "RUE DE LA PAIX" → (None, None)  # Pas de pattern zone
    """
    up = _norm(line).upper()
    
    # Patterns: ZONE INDUSTRIELLE, ZONE COMMERCIALE, PARC, ACTIVITÉ, etc.
    zone_patterns = [
        r"^(ZONE\s+INDUSTRIELLE)\s+(.+)$",
        r"^(ZONE\s+COMMERCIALE)\s+(.+)$",
        r"^(ZONE\s+D'ACTIVITÉ)\s+(.+)$",
        r"^(PARC\s+INDUSTRIEL)\s+(.+)$",
        r"^(PARC\s+COMMERCIAL)\s+(.+)$",
    ]
    
    for pattern in zone_patterns:
        match = re.match(pattern, up)
        if match:
            zone_type = match.group(1)
            remainder = match.group(2).strip()
            
            # Extrait le dernier mot potentiel comme ville
            words = remainder.split()
            if words:
                candidate = words[-1]
                # Exclusions de mots génériques
                if candidate not in {"INDUSTRIELLE", "COMMERCIAL", "D'ACTIVITÉ", "TUNISIE", "TN"}:
                    town_candidate = _clean_town_value(candidate)
                    if town_candidate and len(town_candidate) >= 3:
                        # Reconstruit l'adresse sans le town candidate
                        if len(words) > 1:
                            address_part = " ".join(words[:-1])
                            return (f"{zone_type} {address_part}", town_candidate)
                        else:
                            return (zone_type, town_candidate)
    
    return (None, None)

def _looks_like_real_address_fragment(value):
    up = _norm(value).upper()
    return bool(up) and _contains_address_keyword(up)

def _clean_town_value(town):
    """Nettoie les suffixes parasites. ✅ FIX: ARTIFACTS sans espaces."""
    if not town: return town
    cleaned = _norm(town)
    
    # ✅ FIX: Suppression des espaces dans les strings
    ARTIFACTS = {"->", "→", "??", "N/A", "NA", "NONE", "NULL", "-", "..."}
    if cleaned.upper() in ARTIFACTS: return None
    if re.fullmatch(r"\d{3,8}", cleaned): return None
    
    # Supprime /FR ou -FR en fin
    cleaned = re.sub(r'\s*/\s*[A-Z]{2}\s*$', '', cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'[-–]\s*[A-Z]{2}\s*$', '', cleaned, flags=re.IGNORECASE).strip()
    
    # Supprime code pays ISO en fin (ex: "TUNIS TUNISIE")
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
    """
    Détecte un code pays collé au début d'une ligne (ex: "TNELHAOUARIA" → "TN", "ELHAOUARIA").
    CORRECTIONS :
    - Ignore si le "reste" ressemble à un nom propre (minuscules, espaces)
    - Ignore si la ligne commence par "/" (compte IBAN)
    - Vérifie que le préfixe n'est pas le début d'un mot plus long
    """
    raw = _norm(line)
    up = raw.upper()
    
    # Garde 1: Ligne trop courte ou commence par "/" (compte IBAN)
    if len(up) < 4 or raw.startswith("/"):
        return None, raw
    
    prefix = up[:2]
    if prefix not in COUNTRY_CODES:
        return None, raw
    
    # Garde 2: Liste des préfixes protégés (villes, mots courants)
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
        "TNO", "TNI", "TNE", # Eviter de splitter TNO/TNI si ca design un lieu local
    )
    
    # Garde 3: Si la ligne commence par un mot protégé → pas un pays collé
    if up.startswith(PROTECTED) or up in KNOWN_CITIES:
        return None, raw
    
    # ✅ NOUVELLE GARDE CRITIQUE : Le "reste" ne doit pas ressembler à un nom propre
    rest = raw[2:].strip(" ,-/")
    if not rest or len(rest) < 2:
        return None, raw
    
    # Si le reste contient des minuscules → c'est probablement un nom (ex: "hilips" dans "PHILIPS")
    if any(c.islower() for c in rest):
        return None, raw
    
    # Si le reste contient un espace ET ressemble à un nom complet (ex: "ILIPS MARK")
    if " " in rest and len(rest.split()) >= 2:
        # Vérifier si le premier mot du reste n'est pas une ville connue
        first_word = rest.split()[0].upper()
        if first_word not in KNOWN_CITIES and first_word not in COUNTRY_CODES and rest.upper() not in KNOWN_CITIES:
            return None, raw
    
    # ✅ Dernière vérification: le préfixe doit être suivi d'un séparateur ou d'une majuscule
    # Ex: "TN ELHAOUARIA" (OK) vs "TNELHAOUARIA" (douteux mais accepté si le reste est plausible)
    if len(raw) > 2 and raw[2] not in " -/," and not raw[2].isupper():
        # Si le 3ème caractère n'est pas un séparateur ni une majuscule, c'est suspect
        # Mais on accepte si le reste est court et en majuscules (ex: "TN8045")
        if len(rest) > 10 or any(c.islower() for c in rest):
            return None, raw
    
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
    m = re.match(r"^(\d{3,10})\s+(.+)$", rest)
    if m:
        postal_code = m.group(1).strip()
        town = m.group(2).strip(",")
    else:
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
    """
    Détecte fragments géo dans une ligne.
    Formats supportés:
    - FR/75002 PARIS | FR 75002 PARIS
    - B -6600 BASTOGNE
    - ✅ NOUVEAU: TN ELHAOUARIA 8045 (PAYS VILLE POSTAL)
    - 38100 GRENOBLE
    """
    raw = _norm(line)
    
    # 1. Standard: CC/PC TOWN ou CC PC TOWN
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

    # 2. Format court: B -6600 BASTOGNE
    m = re.search(r"^([A-Za-z]{1,2})\s*[-–]\s*(\d{3,10})\s+([A-Z][A-Z0-9()' .\-]+)$", raw, flags=re.IGNORECASE)
    if m:
        cc = m.group(1).upper().strip()
        if len(cc) == 1: cc = SHORT_COUNTRY_TO_ISO.get(cc, cc)
        if cc in COUNTRY_CODES:
            town = _clean_town_value(_norm(m.group(3)))
            if town: return m.start(), m.end(), CountryTown(country=cc, town=town, postal_code=m.group(2))

    # 3. ✅ NOUVEAU: Format PAYS VILLE POSTAL (ex: TN ELHAOUARIA 8045)
    # On restreint au début de chaîne ou après un séparateur pour éviter de capturer "AVENUE DE PARIS 1000" comme DE (Allemagne)
    m = re.search(r"(?:^|[,/\-]\s*)([A-Z]{2})\s+([A-Z][A-Z0-9()' .\-]+)\s+(\d{3,10})$", raw, flags=re.IGNORECASE)
    if m:
        cc = m.group(1).upper()
        if cc in COUNTRY_CODES:
            town = _clean_town_value(_norm(m.group(2))) # G2 est la ville
            pc = m.group(3)                            # G3 est le postal
            if town: return m.start(), m.end(), CountryTown(country=cc, town=town, postal_code=pc)

    # 4. Format VILLE PROVINCE POSTAL PAYS (ex: QUEBEC QC G1G6L5 CA ou QUEBEC QC G1G 6L5 CA)
    # Match: (Ville et mots) (2 lettres province/état optionnel) (Code postal CA ou standard) (CA/US)
    m = re.search(r"^([A-Z][A-Z0-9()' .\-]+?)\s+(?:[A-Z]{2}\s+)?([A-Z0-9][A-Z0-9\- ]{2,8})\s+(CA|US)$", raw, flags=re.IGNORECASE)
    if m:
        cc = m.group(3).upper()
        if cc in COUNTRY_CODES:
            town = _clean_town_value(_norm(m.group(1)))
            pc = _norm(m.group(2)).replace(" ", "")
            if town: return m.start(), m.end(), CountryTown(country=cc, town=town, postal_code=pc)

    # 5. Postal seul: 38100 GRENOBLE
    m = re.match(r"^(\d{4,6})\s+([A-Z][A-Z0-9()' .\-]+)$", raw, flags=re.IGNORECASE)
    if m:
        town = _clean_town_value(_norm(m.group(2)))
        # Eviter que ça matche de faux numéros de rue (ex: 8846 RUE VALADE)
        if town and not _contains_address_keyword(town): return 0, len(raw), CountryTown(country=None, town=town, postal_code=m.group(1))

    return None
def _apply_iban_and_capital_fallback(geo, iban_country, warnings):
    """IBAN prime pour pays. FALLBACK CAPITALE SUPPRIMÉ pour conformité stricte SR2026."""
    if geo.town:
        geo.town = _clean_town_value(geo.town)
        
    if iban_country:
        if not geo.country:
            geo.country = iban_country
            warnings.append("country_from_iban")
        elif geo.country != iban_country:
            warnings.append(f"country_conflict_iban_hint_only:{iban_country}!=explicit:{geo.country}")
            
    # ⛔ SUPPRESSION DU FALLBACK CAPITALE : Si town est null, il reste null pour quarantaine
    # if geo.country and not geo.town:
    #     capital = CAPITALS.get(geo.country)
    #     if capital:
    #         geo.town = capital
    #         warnings.append(f"town_inferred_from_capital:{geo.country}→{capital}")
    return geo

def _extract_geo_from_free_lines(lines, warnings):
    if not lines: return CountryTown(), 0
    last = _norm(lines[-1])
    up = last.upper()

    # 1. Format JO/JORDANIE
    encoded = _parse_country_encoded_line(last)
    if encoded:
        if encoded.town is None: return encoded, 1
        if _is_known_country_name(encoded.town):
            return CountryTown(country=encoded.country, town=None, postal_code=None), 1

    # 2. Ville connue seule
    if _is_known_city(last): return CountryTown(country=_known_city_country(last), town=last, postal_code=None), 1

    # 3. Fragment pays/postal/ville
    frag = _extract_country_postal_town_fragment(last)
    if frag:
        _, _, ct = frag
        if ct.country or ct.postal_code: return ct, 1

    # 4. Format pays court avec tiret: B -6600 BASTOGNE
    m_short = re.match(r"^([A-Za-z]{1,2})\s*[-–]?\s*(\d{4,6})\s+(.+)$", last, flags=re.IGNORECASE)
    if m_short:
        cc = m_short.group(1).upper().strip()
        if len(cc) == 1: cc = SHORT_COUNTRY_TO_ISO.get(cc, cc)
        if cc in COUNTRY_CODES:
            town = _clean_town_value(_norm(m_short.group(3)))
            if town:
                warnings.append(f"short_country_code_normalized:{m_short.group(1).upper()}→{cc}")
                return CountryTown(country=cc, town=town, postal_code=m_short.group(2)), 1

    # 5. Pays connu (nom complet ou code)
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
            
            # ✅ CORRECTION CRITIQUE : Gestion des Zones Industrielles / Commerciales safely
            _, town_from_zone = _extract_town_from_zone_line(prev)
            if town_from_zone:
                return CountryTown(country=code, town=town_from_zone, postal_code=None), 2

            m = re.match(r"^(\d{4,6})\s+(.+)$", prev)
            if m:
                town = _clean_town_value(m.group(2).strip())
                if town and not _contains_address_keyword(town):
                    return CountryTown(country=code, town=town, postal_code=m.group(1).strip()), 2
            
            if prev and (not _is_address(prev)):
                return CountryTown(country=code, town=_clean_town_value(prev), postal_code=None), 2
        
        return CountryTown(country=code, town=None, postal_code=None), 1

    # 6. Fin de ligne = "VILLE PAYS"
    for name, code in COUNTRY_NAME_TO_CODE.items():
        suffix = " " + name
        if up.endswith(suffix):
            town = _clean_town_value(last[:-len(suffix)].strip())
            return CountryTown(country=code, town=town or None, postal_code=None), 1 

    # 7. Pays collé (TN...)
    embedded_country, cleaned_town = _split_embedded_country_prefix(last)
    if embedded_country and cleaned_town:
        cleaned_cc = resolve_country_code(cleaned_town)
        if cleaned_cc == embedded_country:
            return CountryTown(country=embedded_country, town=None, postal_code=None), 1
        warnings.append(f"country_embedded_in_town_line:{embedded_country}")
        town = _clean_town_value(cleaned_town)
        return CountryTown(country=embedded_country, town=town, postal_code=None), 1

    # 8. Postal seul
    m = re.match(r"^(\d{4,6})\s+(.+)$", last)
    if m:
        town = _clean_town_value(m.group(2).strip())
        if town and not _contains_address_keyword(town):
            return CountryTown(country=None, town=town, postal_code=m.group(1).strip()), 1

    return CountryTown(country=None, town=_clean_town_value(last), postal_code=None), 1


def parse_free_party_field(pre, field_type, role, message_id):
    """Parse un champ libre (50K/59) avec conservation stricte des lignes adresses."""
    res = _empty(field_type, role, message_id, raw=pre.normalized_text or pre.raw_input)
    warnings = res.meta.warnings
    lines = pre.lines[:]
    idx = 0
    iban_country = pre.meta.iban_country

    # 1. Extraction du compte
    if lines and lines[0].startswith("/"):
        res.account = lines[0]
        idx = 1

    content = [_norm(x) for x in lines[idx:] if _norm(x)]
    if not content:
        warnings.append("no_content_after_account")
        res.meta.parse_confidence = 0.0
        return res

    # 2. CAS SPÉCIAL : une seule ligne finissant par un pays
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

    # 3. Extraction géographique
    geo, consumed = _extract_geo_from_free_lines(content, warnings)

    # ✅ CORRECTION CRITIQUE : Ne consomme QUE les lignes strictement géographiques
    if consumed > 0 and content:
        indices_to_remove = []
        for i in range(consumed):
            line_idx = len(content) - 1 - i
            if line_idx >= 0:
                line = content[line_idx]
                # Si la ligne contient un mot-clé adresse (CITE, ZONE, RUE...), on la garde
                if not _contains_address_keyword(line):
                    indices_to_remove.append(line_idx)
        
        # Suppression sécurisée (indices décroissants)
        for idx in sorted(indices_to_remove, reverse=True):
            content.pop(idx)

    geo = _apply_iban_and_capital_fallback(geo, iban_country, warnings)
    if not content:
        res.country_town = geo
        res.address_lines = _deduplicate_addresses(res.address_lines)
        res.is_org = _detect_org(res.name)
        res.meta.parse_confidence = 0.80
        return res

    # 4. Parsing du NOM
    first = content[0]
    split_name, split_addr = _split_inline_name_address(first)
    if split_addr:
        res.name = [split_name]
        res.address_lines.append(split_addr)
        warnings.append("name_address_mixed")
    else:
        res.name = [first]

    remaining = content[1:]

    # Continuation org multi-ligne
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

    # 5. CAS SPÉCIAL : [ligne candidate] + [pays]
    if len(remaining) == 2:
        line1 = _norm(remaining[0])
        line2 = _norm(remaining[1]).upper()
        line2_country = resolve_country_code(line2)
        if line2_country:
            # ✅ EXTRACTION ZONE INDUSTRIELLE: "ZONE INDUSTRIELLE ENFIDHA" → town="ENFIDHA"
            addr_part, town_from_zone = _extract_town_from_zone_line(line1)
            if addr_part and town_from_zone and _is_known_city(town_from_zone):
                # Zone industrielle avec ville: ajouter adresse, mettre town
                if addr_part != "":
                    res.address_lines.append(addr_part)
                res.country_town = _apply_iban_and_capital_fallback(
                    CountryTown(country=line2_country, town=town_from_zone, postal_code=None),
                    iban_country, warnings
                )
                res.address_lines = _deduplicate_addresses(res.address_lines)
                warnings.append(f"zone_industrielle_extracted_town:{town_from_zone}")
                res.is_org = _detect_org(res.name)
                res.meta.parse_confidence = 0.85
                return res
            
            m = re.match(r"^(\d{4,6})\s+(.+)$", line1)
            if m:
                town = _clean_town_value(m.group(2).strip())
                if town and not _contains_address_keyword(town):
                    res.country_town = _apply_iban_and_capital_fallback(
                        CountryTown(country=line2_country, town=town, postal_code=m.group(1).strip()),
                        iban_country, warnings
                    )
                    res.address_lines = _deduplicate_addresses(res.address_lines)
                    res.is_org = _detect_org(res.name)
                    res.meta.parse_confidence = 0.85
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

    # 6. Traitement des lignes restantes
    for line in remaining:
        line = _norm(line)
        if _is_postal_town_line(line, geo):
            continue
        
        frag = _extract_country_postal_town_fragment(line)
        if frag:
            start_idx, _, ct = frag
            if not geo.country: geo.country = ct.country
            if not geo.town: geo.town = _clean_town_value(ct.town)
            if not geo.postal_code: geo.postal_code = ct.postal_code
            addr_part = _norm(line[:start_idx]).strip(" ,-/")
            if addr_part:
                res.address_lines.append(addr_part)
            continue
            
        if geo.town and _norm(line).upper() == _norm(geo.town).upper():
            continue
            
        line_country = resolve_country_code(line)
        if line_country:
            if not geo.country: geo.country = line_country
            continue
            
        res.address_lines.append(line) 
        if not _is_address(line):
            warnings.append(f"unclassified_line_to_address:{line}")

    # 7. Reclassification : si la ville extraite ressemble à une adresse
    if geo.town and _looks_like_real_address_fragment(geo.town):
        if geo.town not in res.address_lines:
            res.address_lines.insert(0, geo.town)
        geo.town = None
        warnings.append("town_reclassified_as_address")

    # 8. Finalisation
    geo = _apply_iban_and_capital_fallback(geo, iban_country, warnings)
    res.address_lines = _deduplicate_addresses(res.address_lines)
    res.country_town = geo
    res.is_org = _detect_org(res.name)

    # Calcul de la confiance
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
