"""src/e2_address_fragmentation.py — Fragmentation d'adresse vers ISO 20022
ALIGNÉ AVEC: e2_address_parser.py (Clés MAJUSCULES, Valeurs avec espaces)
"""
from typing import Optional, List, Dict, Any
from src.models import CanonicalParty, FragmentedAddress
from src.e2_address_parser import parse_address_line
from src.logger import StepLogger

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