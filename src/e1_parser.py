"""e1_parser.py — Étape E1 : Parsing structuré et libre des champs SWIFT"""

import re
from typing import List, Optional, Tuple

from src.models import (
    CanonicalParty, CanonicalMeta, CountryTown, PlaceOfBirth,
    PartyIdentifier, PreprocessResult,
)
from src.reference_data import (
    COUNTRY_NAME_TO_CODE, COUNTRY_CODES, ADDRESS_KEYWORDS, ORG_HINTS,
    PARTY_ID_PREFIXES, CAPITALS, CITIES_BY_COUNTRY,
)
from src.ambiguity_resolver import resolve_city_country_ambiguity


def _norm(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.strip())


def _empty(field_type: str, role: str, message_id: str) -> CanonicalParty:
    return CanonicalParty(
        message_id=message_id,
        field_type=field_type,
        role=role,
        meta=CanonicalMeta(source_format=field_type, parse_confidence=0.0),
    )


def _all_known_cities_upper() -> set:
    result = set()
    for _, cities in CITIES_BY_COUNTRY.items():
        for city in cities:
            result.add(_norm(city).upper())
    return result


KNOWN_CITIES = _all_known_cities_upper()


def _is_known_country_name(line: str) -> bool:
    return _norm(line).upper() in COUNTRY_NAME_TO_CODE


def _is_known_city(line: str) -> bool:
    return _norm(line).upper() in KNOWN_CITIES


def _is_address(line: str) -> bool:
    up = _norm(line).upper()
    if any(k in up for k in ADDRESS_KEYWORDS):
        return True
    if re.search(r"\d", up):
        return True
    return False


def _looks_like_real_address_fragment(value: str) -> bool:
    up = _norm(value).upper()
    if not up:
        return False
    has_keyword = any(k in up for k in ADDRESS_KEYWORDS)
    has_digit = bool(re.search(r"\d", up))
    if has_keyword:
        return True
    if has_digit and has_keyword:
        return True
    return False


def _detect_org(name_lines: List[str]) -> Optional[bool]:
    txt = " ".join(name_lines).upper()
    if any(k in txt for k in ORG_HINTS):
        return True
    words = txt.split()
    if len(words) == 2 and all(re.fullmatch(r"[A-Z.\-]+", w) for w in words):
        return False
    return None


def _deduplicate_addresses(address_lines: List[str]) -> List[str]:
    result: List[str] = []
    for line in address_lines:
        line = _norm(line)
        if not line:
            continue
        skip = False
        to_remove = []
        for existing in result:
            ex_norm = _norm(existing).upper()
            cur_norm = line.upper()
            if cur_norm == ex_norm:
                skip = True
                break
            if ex_norm in cur_norm:
                skip = True
                break
            if cur_norm in ex_norm:
                to_remove.append(existing)
        if skip:
            continue
        for item in to_remove:
            if item in result:
                result.remove(item)
        result.append(line)
    return result

def _is_postal_town_line(line: str, geo: CountryTown) -> bool:
    """
    Retourne True si la ligne est redondante avec le country_town déjà extrait.
    Ex: '10117 BERLIN' quand on a déjà postal_code=10117 et town=BERLIN
    """
    if not geo:
        return False

    line_n = _norm(line).upper()

    # Cas 1 : ligne = "CODE_POSTAL VILLE"
    if geo.postal_code and geo.town:
        candidate = f"{geo.postal_code} {_norm(geo.town).upper()}"
        if line_n == candidate:
            return True

    # Cas 2 : ligne = juste la ville
    if geo.town and line_n == _norm(geo.town).upper():
        return True

    # Cas 3 : ligne = juste le code postal
    if geo.postal_code and line_n == geo.postal_code:
        return True

    return False

def _parse_party_identifier(raw: str) -> PartyIdentifier:
    parts = [p.strip() for p in raw.split("/") if p.strip()]
    code = parts[0].upper() if len(parts) >= 1 else None
    country = parts[1].upper() if len(parts) >= 2 else None
    issuer = None
    identifier = None
    if code in {"NIDN", "CCPT", "ARNU", "SOSE", "TXID"}:
        identifier = parts[2] if len(parts) >= 3 else None
    elif code in {"CUST", "DRLC", "EMPL"}:
        issuer = parts[2] if len(parts) >= 3 else None
        identifier = parts[3] if len(parts) >= 4 else None
    else:
        if len(parts) >= 3:
            identifier = parts[-1]
    return PartyIdentifier(code=code, country=country, issuer=issuer, identifier=identifier)


def _split_embedded_country_prefix(line: str) -> Tuple[Optional[str], str]:
    raw = _norm(line)
    up = raw.upper()
    if len(up) < 4:
        return None, raw
    prefix = up[:2]
    if prefix not in COUNTRY_CODES:
        return None, raw
    if re.match(r"^(BER|BEL|BEN|BRU)", up):
        return None, raw
    rest = raw[2:].strip(" ,-/")
    if not rest:
        return None, raw
    return prefix, rest


def _split_inline_name_address(line: str) -> Tuple[str, Optional[str]]:
    raw = _norm(line)
    up = raw.upper()
    match = re.search(
        r"\b(RUE|AVENUE|AVE|STREET|ROAD|ROUTE|STRASSE|BOULEVARD|BD|ZONE|CITE|IMMEUBLE|IMM|APT|APPT|LANE|DRIVE|WAY)\b",
        up,
    )
    if not match:
        return raw, None
    idx = match.start()
    left = raw[:idx].strip(" ,-/")
    right = raw[idx:].strip(" ,-/")
    if not left or not right:
        return raw, None
    return left, _norm(right)


def _looks_like_org_continuation(line: str) -> bool:
    up = _norm(line).upper()
    if _is_known_city(up):
        return False
    if _is_known_country_name(up):
        return False
    if _is_address(up):
        return False
    words = up.split()
    if not words:
        return False
    if len(words) <= 3 and any(w in ORG_HINTS for w in words):
        return True
    if len(words) <= 3 and all(re.fullmatch(r"[A-Z.&\-]+", w) for w in words):
        return True
    return False


def _parse_structured_country_town(value: str) -> Tuple[Optional[CountryTown], bool]:
    raw = _norm(value)
    parts = [p.strip() for p in raw.split("/")]
    if len(parts) == 1:
        return None, False
    country = parts[0].upper()
    rest = parts[1]
    if country not in COUNTRY_CODES:
        return None, False
    postal_code = None
    town = rest
    m = re.match(r"^(.*?)(?:\s+([0-9A-Z\-]{3,10}))$", rest)
    if m and re.search(r"\d", m.group(2)):
        town = m.group(1).strip(" ,")
        postal_code = m.group(2).strip()
    return CountryTown(country=country, town=town or None, postal_code=postal_code), True


def _parse_place_of_birth(value: str) -> PlaceOfBirth:
    raw = _norm(value)
    parts = [p.strip() for p in raw.split("/")]
    if len(parts) >= 2:
        return PlaceOfBirth(country=parts[0].upper(), city=parts[1])
    return PlaceOfBirth(country=None, city=raw or None)


def _extract_country_postal_town_fragment(line: str) -> Optional[Tuple[int, int, CountryTown]]:
    raw = _norm(line)
    patterns = [
        r"\b([A-Z]{2})/(\d{3,10})\s+([A-Z0-9()' .\-]+)$",
        r"\b([A-Z]{2})\s+(\d{3,10})\s+([A-Z0-9()' .\-]+)$",
    ]
    for pattern in patterns:
        m = re.search(pattern, raw, flags=re.IGNORECASE)
        if not m:
            continue
        cc = m.group(1).upper()
        pc = m.group(2)
        town = _norm(m.group(3))
        if cc in COUNTRY_CODES:
            return m.start(), m.end(), CountryTown(country=cc, town=town, postal_code=pc)
    return None


def _extract_geo_from_free_lines(lines: List[str], warnings: List[str]) -> Tuple[CountryTown, int]:
    if not lines:
        return CountryTown(), 0

    last = _norm(lines[-1])
    up = last.upper()

    frag = _extract_country_postal_town_fragment(last)
    if frag:
        start_idx, end_idx, ct = frag
        frag_text = _norm(last[start_idx:end_idx])
        if _norm(last).upper() == frag_text.upper():
            return ct, 1

    for name, code in COUNTRY_NAME_TO_CODE.items():
        if up == name:
            if len(lines) >= 2:
                prev = _norm(lines[-2])
                frag_prev = _extract_country_postal_town_fragment(prev)
                if frag_prev:
                    start_idx, end_idx, ct_prev = frag_prev
                    frag_text = _norm(prev[start_idx:end_idx])
                    if _norm(prev).upper() == frag_text.upper():
                        if ct_prev.country == code or ct_prev.country is None:
                            ct_prev.country = code
                        return ct_prev, 2
                m = re.match(r"^(\d{4,6})\s+(.+)$", prev)
                if m:
                    return CountryTown(country=code, town=m.group(2).strip(), postal_code=m.group(1).strip()), 2
                if prev and not _is_address(prev):
                    return CountryTown(country=code, town=prev, postal_code=None), 2
            return CountryTown(country=code, town=None, postal_code=None), 1

    for name, code in COUNTRY_NAME_TO_CODE.items():
        suffix = " " + name
        if up.endswith(suffix):
            town = last[: -len(suffix)].strip()
            return CountryTown(country=code, town=town or None, postal_code=None), 1

    embedded_country, cleaned_town = _split_embedded_country_prefix(last)
    if embedded_country and cleaned_town:
        warnings.append(f"country_embedded_in_town_line:{embedded_country}")
        return CountryTown(country=embedded_country, town=cleaned_town, postal_code=None), 1

    m = re.match(r"^(\d{4,6})\s+(.+)$", last)
    if m:
        return CountryTown(country=None, town=m.group(2).strip(), postal_code=m.group(1).strip()), 1

    return CountryTown(country=None, town=last, postal_code=None), 1


def parse_free_party_field(pre: PreprocessResult, field_type: str, role: str, message_id: str) -> CanonicalParty:
    res = _empty(field_type, role, message_id)
    warnings = res.meta.warnings
    lines = pre.lines[:]
    idx = 0

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
                left = only_line[: -len(suffix)].strip()
                if left:
                    res.name = [left]
                    res.country_town = CountryTown(country=country_code, town=None, postal_code=None)
                    warnings.append("town_missing_from_name_country_pattern")
                    if pre.meta.iban_country and not res.country_town.country:
                        res.country_town.country = pre.meta.iban_country
                        warnings.append("country_from_iban")
                    res.is_org = _detect_org(res.name)
                    res.meta.parse_confidence = 0.85
                    return res

    # DÉTECTION GÉO EN PRIORITÉ
    geo, consumed = _extract_geo_from_free_lines(content, warnings)

    if consumed > 0 and content:
        last_line = _norm(content[-1])
        frag = _extract_country_postal_town_fragment(last_line)
        pure_geo_line = False
        if frag:
            start_idx, end_idx, _ = frag
            frag_text = _norm(last_line[start_idx:end_idx])
            if frag_text.upper() == last_line.upper():
                pure_geo_line = True
        else:
            if not _is_address(last_line):
                pure_geo_line = True
        if pure_geo_line:
            content = content[:-consumed]

    if not content:
        res.country_town = geo
        if pre.meta.iban_country and not res.country_town.country:
            res.country_town.country = pre.meta.iban_country
            warnings.append("country_from_iban")
        if res.country_town.country and not res.country_town.town:
            capital = CAPITALS.get(res.country_town.country)
            if capital:
                res.country_town.town = capital
                warnings.append(f"town_inferred_from_capital:{res.country_town.country}→{capital}")
        res.address_lines = _deduplicate_addresses(res.address_lines)
        res.is_org = _detect_org(res.name)
        res.meta.parse_confidence = 0.80
        return res

    # NOM INITIAL
    first = content[0]
    split_name, split_addr = _split_inline_name_address(first)
    if split_addr:
        res.name = [split_name]
        res.address_lines.append(split_addr)
        warnings.append("name_address_mixed")
    else:
        res.name = [first]

    remaining = content[1:]

    # continuation org multi-ligne
    if remaining:
        candidate = _norm(remaining[0])
        looks_geo = False
        if _is_known_city(candidate):
            looks_geo = True
        if _is_known_country_name(candidate):
            looks_geo = True
        up_candidate = candidate.upper()
        for country_name in COUNTRY_NAME_TO_CODE.keys():
            suffix = " " + country_name
            if up_candidate.endswith(suffix):
                looks_geo = True
                break
        if not looks_geo and _looks_like_org_continuation(candidate):
            res.name[0] = f"{res.name[0]} {candidate}".strip()
            remaining = remaining[1:]
            warnings.append("multiline_name_fused:1")

    # CAS SPÉCIAL 2 : [ligne candidate] + [pays]
    if len(remaining) == 2:
        line1 = _norm(remaining[0])
        line2 = _norm(remaining[1]).upper()
        if line2 in COUNTRY_NAME_TO_CODE:
            m = re.match(r"^(\d{4,6})\s+(.+)$", line1)
            if m:
                res.country_town = CountryTown(
                    country=COUNTRY_NAME_TO_CODE[line2],
                    town=m.group(2).strip(),
                    postal_code=m.group(1).strip(),
                )
                res.address_lines = _deduplicate_addresses(res.address_lines)
                res.is_org = _detect_org(res.name)
                res.meta.parse_confidence = 0.88
                return res

            decision = resolve_city_country_ambiguity(line1, line2)
            if decision.label == "TOWN":
                res.country_town = CountryTown(country=COUNTRY_NAME_TO_CODE[line2], town=line1, postal_code=None)
                res.address_lines = _deduplicate_addresses(res.address_lines)
                warnings.append(f"ambiguous_city_country_tail_resolved_as_town:{decision.reason}")
                res.is_org = _detect_org(res.name)
                res.meta.parse_confidence = decision.confidence
                return res
            if decision.label == "ADDRESS":
                res.address_lines.append(line1)
                res.country_town = CountryTown(country=COUNTRY_NAME_TO_CODE[line2], town=None, postal_code=None)
                res.address_lines = _deduplicate_addresses(res.address_lines)
                warnings.append(f"ambiguous_city_country_tail_resolved_as_address:{decision.reason}")
                res.is_org = _detect_org(res.name)
                res.meta.parse_confidence = decision.confidence
                return res
            res.country_town = CountryTown(country=COUNTRY_NAME_TO_CODE[line2], town=line1, postal_code=None)
            res.address_lines = _deduplicate_addresses(res.address_lines)
            warnings.append("ambiguous_city_country_tail")
            res.is_org = _detect_org(res.name)
            res.meta.parse_confidence = 0.65
            return res

    # analyser les lignes restantes
    for line in remaining:
        line = _norm(line)
        # ✅ NOUVEAU : ignorer les lignes redondantes avec geo déjà extrait
        if _is_postal_town_line(line, geo):
            continue
        frag = _extract_country_postal_town_fragment(line)
        if frag:
            start_idx, _, ct = frag
            if not geo.country:
                geo.country = ct.country
            if not geo.town:
                geo.town = ct.town
            if not geo.postal_code:
                geo.postal_code = ct.postal_code
            addr_part = _norm(line[:start_idx]).strip(" ,-/")
            if addr_part:
                res.address_lines.append(addr_part)
            continue
        if geo.town and _norm(line).upper() == _norm(geo.town).upper():
            continue
        if line.upper() in COUNTRY_NAME_TO_CODE:
            if not geo.country:
                geo.country = COUNTRY_NAME_TO_CODE[line.upper()]
            continue
        if _is_address(line):
            res.address_lines.append(line)
        else:
            res.address_lines.append(line)
            warnings.append(f"unclassified_line_to_address:{line}")

    if geo.town and _looks_like_real_address_fragment(geo.town):
        if geo.town not in res.address_lines:
            res.address_lines.insert(0, geo.town)
        geo.town = None
        warnings.append("town_reclassified_as_address")

    if pre.meta.iban_country:
        if not geo.country:
            geo.country = pre.meta.iban_country
            warnings.append("country_from_iban")

    if geo.country and not geo.town:
        capital = CAPITALS.get(geo.country)
        if capital:
            geo.town = capital
            warnings.append(f"town_inferred_from_capital:{geo.country}→{capital}")

    res.address_lines = _deduplicate_addresses(res.address_lines)
    res.country_town = geo
    res.is_org = _detect_org(res.name)

    confidence = 0.90
    if "name_address_mixed" in warnings:
        confidence -= 0.05
    if any(w.startswith("multiline_name_fused") for w in warnings):
        confidence -= 0.05
    if "town_reclassified_as_address" in warnings:
        confidence -= 0.10
    if any(w.startswith("town_inferred_from_capital") for w in warnings):
        confidence -= 0.10
    if any(w.startswith("unclassified_line_to_address:") for w in warnings):
        confidence -= 0.05
    if "town_missing_from_name_country_pattern" in warnings:
        confidence -= 0.05
    if "ambiguous_city_country_tail" in warnings:
        confidence -= 0.10

    res.meta.parse_confidence = max(0.0, round(confidence, 2))
    return res


def parse_structured_50F(pre: PreprocessResult, message_id: str = "MSG") -> CanonicalParty:
    res = _empty("50F", "debtor", message_id)
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

    has_4 = False
    has_5 = False
    seen_3 = False

    for line in lines[idx:]:
        if "/" not in line:
            continue
        tag, value = line.split("/", 1)
        tag = tag.strip()
        value = _norm(value)

        if tag == "1":
            res.name.append(value)
        elif tag == "2":
            res.address_lines.append(value)
        elif tag == "3":
            parsed_ct, ok = _parse_structured_country_town(value)
            if ok and parsed_ct:
                res.country_town = parsed_ct
                seen_3 = True
            else:
                res.country_town = CountryTown(country=None, town=value, postal_code=None)
                warnings.append("invalid_structured_line_3")
        elif tag == "4":
            res.dob = value
            has_4 = True
        elif tag == "5":
            res.pob = _parse_place_of_birth(value)
            has_5 = True
        elif tag == "6":
            parts = [p.strip() for p in value.split("/")]
            if len(parts) >= 3:
                res.org_id = PartyIdentifier(code="CUST", country=parts[0].upper(), issuer=parts[1], identifier=parts[2])
        elif tag == "7":
            parts = [p.strip() for p in value.split("/")]
            if len(parts) >= 2:
                res.national_id = parts[1]
            else:
                res.national_id = value
        elif tag == "8":
            res.postal_complement = value

    if not seen_3 and "invalid_structured_line_3" not in warnings:
        warnings.append("missing_mandatory_3")
    if has_4 != has_5:
        warnings.append("4_and_5_must_appear_together")

    res.is_org = _detect_org(res.name)
    confidence = 1.0
    if "missing_mandatory_3" in warnings:
        confidence -= 0.30
    if "invalid_structured_line_3" in warnings:
        confidence -= 0.25
    if "4_and_5_must_appear_together" in warnings:
        confidence -= 0.20
    res.meta.parse_confidence = max(0.0, round(confidence, 2))
    return res


def parse_structured_59F(pre: PreprocessResult, message_id: str = "MSG") -> CanonicalParty:
    res = _empty("59F", "creditor", message_id)
    warnings = res.meta.warnings
    lines = pre.lines[:]
    idx = 0

    if lines and lines[0].startswith("/"):
        res.account = lines[0]
        idx = 1

    seen_3 = False

    for line in lines[idx:]:
        if "/" not in line:
            continue
        tag, value = line.split("/", 1)
        tag = tag.strip()
        value = _norm(value)

        if tag == "1":
            res.name.append(value)
        elif tag == "2":
            res.address_lines.append(value)
        elif tag == "3":
            parsed_ct, ok = _parse_structured_country_town(value)
            if ok and parsed_ct:
                res.country_town = parsed_ct
                seen_3 = True
            else:
                if value.upper() in COUNTRY_CODES:
                    res.country_town = CountryTown(country=value.upper(), town=None, postal_code=None)
                    seen_3 = True
                else:
                    warnings.append("invalid_structured_line_3")

    if not seen_3 and "invalid_structured_line_3" not in warnings:
        warnings.append("missing_mandatory_3")

    res.is_org = _detect_org(res.name)
    confidence = 1.0
    if "missing_mandatory_3" in warnings:
        confidence -= 0.30
    if "invalid_structured_line_3" in warnings:
        confidence -= 0.25
    res.meta.parse_confidence = max(0.0, round(confidence, 2))
    return res


def parse_field(pre: PreprocessResult, message_id: str = "MSG") -> CanonicalParty:
    t = (pre.meta.detected_field_type or "").upper()

    if t == "50K":
        return parse_free_party_field(pre, "50K", "debtor", message_id)
    if t == "59":
        return parse_free_party_field(pre, "59", "creditor", message_id)
    if t == "50F":
        return parse_structured_50F(pre, message_id)
    if t == "59F":
        return parse_structured_59F(pre, message_id)

    raise Exception(f"Type non supporté: {t}")
