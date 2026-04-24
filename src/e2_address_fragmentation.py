"""src/e2_address_fragmentation.py — Fragmentation d'adresse vers ISO 20022
ALIGNÉ AVEC: e2_address_parser.py (Clés MAJUSCULES, Valeurs avec espaces)
"""
import re
from typing import Optional, List, Dict, Any
from src.models import CanonicalParty, FragmentedAddress
from src.e2_address_parser import parse_address_line
from src.logger import StepLogger


def _contains_cjk(text: Optional[str]) -> bool:
    if not text:
        return False
    return bool(re.search(r"[\u4e00-\u9fff]", str(text)))


def _extract_chinese_fragment(line: str, country_hint: Optional[str]) -> Optional[FragmentedAddress]:
    raw = (line or "").strip()
    if not raw or (country_hint and str(country_hint).upper() != "CN") and not _contains_cjk(raw):
        return None

    if not _contains_cjk(raw):
        return None

    postal = None
    postal_match = re.search(r"(?:邮编|郵編|ZIP|POSTCODE|POSTAL\s*CODE|CODE\s*POSTAL)\s*[:：-]?\s*(\d{4,10})", raw, re.IGNORECASE)
    if postal_match:
        postal = postal_match.group(1)

    city_match = re.match(
        r"^(?P<city>[\u4e00-\u9fff]{2,10}?市)(?P<district>[\u4e00-\u9fff]{2,10}(?:区|县|旗))?(?P<rest>.*)$",
        raw,
    )
    if not city_match:
        city_match = re.match(
            r"^(?P<district>[\u4e00-\u9fff]{2,10}(?:区|县|旗))(?P<rest>.*)$",
            raw,
        )

    if not city_match:
        if postal:
            return FragmentedAddress(pst_cd=postal, ctry=country_hint, fragmentation_confidence=0.65, fallback_used=True)
        return None

    city = city_match.groupdict().get("city") or None
    district = (city_match.groupdict().get("district") or None)
    if district:
        district = re.sub(r"\s+", "", district)
    rest = (city_match.groupdict().get("rest") or "").strip(" ，,;：:·")

    # Normalize city to a usable town. Keep the raw Chinese city name.
    town = city or district
    if town and town.endswith("市"):
        town = town

    strt_nm = None
    bldg_nb = None
    bldg_nm = None
    flr = None
    room = None

    street_match = re.search(r"(.+?(?:路|街|道|巷|大街|大道|胡同|弄|里))\s*(\d+[号弄]?)(.*)$", rest)
    if street_match:
        strt_nm = street_match.group(1).strip()
        bldg_nb = street_match.group(2).strip()
        rest = (street_match.group(3) or "").strip()

    floor_match = re.search(r"(\d+)\s*层", rest)
    if floor_match:
        flr = floor_match.group(1)

    building_match = re.search(r"(.+?(?:座|栋|楼|中心|大厦))(?:(\d+)\s*层)?$", rest)
    if building_match:
        bldg_nm = building_match.group(1).strip()
        if not flr and building_match.group(2):
            flr = building_match.group(2)
    elif rest:
        bldg_nm = rest or None

    return FragmentedAddress(
        strt_nm=strt_nm,
        bldg_nb=bldg_nb,
        bldg_nm=bldg_nm,
        flr=flr,
        room=room,
        pst_cd=postal,
        twn_nm=town,
        ctry_sub_div=re.sub(r"\s+", "", district) if district else None,
        ctry=(country_hint.upper() if country_hint else None),
        fragmentation_confidence=0.82,
        fallback_used=True,
    )

def _is_artifact(value: Optional[str]) -> bool:
    if not value: return True
    v = str(value).strip()
    return v in {"->", "→", "??", "N/A", "NA", "NONE", "NULL", "-", "..."}

def _safe_hint(value: Optional[str]) -> Optional[str]:
    if _is_artifact(value): return None
    return value

def _get_comp(components: Dict[str, Any], *keys: str) -> Optional[str]:
    """Récupère une valeur en essayant plusieurs clés (MAJ/min)."""
    for key in keys:
        if key in components:
            val = components[key]
            return val if isinstance(val, str) else (val[0] if isinstance(val, list) and val else None)
        key_upper = key.upper()
        if key_upper in components:
            val = components[key_upper]
            return val if isinstance(val, str) else (val[0] if isinstance(val, list) and val else None)
    return None

def _map_libpostal_to_iso(
    components: Dict[str, Any],
    country_hint: Optional[str] = None,
    postal_code_hint: Optional[str] = None,
    town_hint: Optional[str] = None,
) -> FragmentedAddress:
    """Mapping libpostal → ISO 20022 avec gestion intelligente des clés."""
    
    strt_nm = _get_comp(components, "road", "ROAD")
    bldg_nb = _get_comp(components, "house_number", "HOUSE_NUMBER")
    bldg_nm = _get_comp(components, "house_name", "HOUSE_NAME", "house", "HOUSE")
    room = _get_comp(components, "unit", "UNIT", "room", "ROOM")

    if bldg_nb and not re.search(r"\d", str(bldg_nb)):
        bldg_nm = bldg_nm or bldg_nb
        bldg_nb = None
    
    pst_cd = _get_comp(components, "postcode", "POSTCODE") or _safe_hint(postal_code_hint)
    twn_nm = _safe_hint(town_hint) or _get_comp(components, "city", "CITY")
    ctry_sub_div = _get_comp(components, "state", "STATE", "suburb", "SUBURB")
    ctry = _safe_hint(country_hint) or _get_comp(components, "country", "COUNTRY")

    iso_fields_filled = any([strt_nm, bldg_nb, bldg_nm, room, pst_cd, twn_nm])

    if iso_fields_filled:
        return FragmentedAddress(
            strt_nm=strt_nm, bldg_nb=bldg_nb, bldg_nm=bldg_nm, room=room,
            pst_cd=pst_cd, twn_nm=twn_nm, ctry_sub_div=ctry_sub_div, ctry=ctry,
            fragmentation_confidence=0.92, fallback_used=False,
        )
    # ✅ Nettoyage des suffixes pays dans twn_nm
    if twn_nm:
        twn_nm = re.sub(r'\s*/\s*[A-Z]{2}\s*$', '', twn_nm, flags=re.IGNORECASE).strip()
        twn_nm = re.sub(r'\s+[A-Z]{2}\s*$', '', twn_nm, flags=re.IGNORECASE).strip()
        twn_nm = twn_nm or None  # Si vide après nettoyage
    
    return FragmentedAddress(
        adr_line=list(components.values()) if components else [],
        pst_cd=_safe_hint(postal_code_hint),
        twn_nm=_safe_hint(town_hint),
        ctry=_safe_hint(country_hint),
        fragmentation_confidence=0.55, fallback_used=True,
    )

def _fragment_single_line(
    line: str,
    country_hint: Optional[str] = None,
    postal_code_hint: Optional[str] = None,
    town_hint: Optional[str] = None,
) -> FragmentedAddress:
    chinese_fragment = _extract_chinese_fragment(line, country_hint)
    if chinese_fragment:
        if not chinese_fragment.pst_cd:
            chinese_fragment.pst_cd = _safe_hint(postal_code_hint)
        if not chinese_fragment.twn_nm:
            chinese_fragment.twn_nm = _safe_hint(town_hint)
        return chinese_fragment

    try:
        parsed = parse_address_line(line)
        components = parsed.get("components", {})
        if parsed.get("is_valid") and components:
            return _map_libpostal_to_iso(
                components, country_hint, postal_code_hint, town_hint,
            )
    except Exception: pass

    return FragmentedAddress(
        adr_line=[line],
        pst_cd=_safe_hint(postal_code_hint),
        twn_nm=_safe_hint(town_hint),
        ctry=_safe_hint(country_hint),
        fragmentation_confidence=0.55, fallback_used=True,
    )

def fragment_party_address(party: CanonicalParty) -> CanonicalParty:
    logger = StepLogger(enabled=False)
    if not party.address_lines:
        party.fragmented_addresses = []
        return party

    fragmented: List[FragmentedAddress] = []
    ct = party.country_town
    c_hint = _safe_hint(ct.country) if ct else None
    t_hint = _safe_hint(ct.town) if ct else None
    p_hint = _safe_hint(ct.postal_code) if ct else None

    for line in party.address_lines:
        frag = _fragment_single_line(line, c_hint, p_hint, t_hint)
        fragmented.append(frag)
        if frag.fallback_used:
            logger.warn(f"Fallback AdrLine: {line[:40]}...")

    party.fragmented_addresses = fragmented
    return party
