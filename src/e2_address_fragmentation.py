"""src/e2_address_fragmentation.py — Fragmentation d'adresse vers ISO 20022"""
from typing import Optional, List, Dict, Any
from src.models import CanonicalParty, FragmentedAddress
from src.e2_address_parser import parse_address_line
from src.logger import StepLogger

NON_RESIDENTIAL_KEYWORDS = {"ZONE", "CITE", "CITÉ", "QUARTIER", "SECTEUR", "INDUSTRIELLE", "INDUSTRIAL", "COMMERCIALE", "IMMEUBLE", "IMM", "BLOC"}

def _safe_hint(value: Optional[str]) -> Optional[str]:
    if not value: return None
    v = str(value).strip()
    return None if v in {"->", "→", "??", "N/A", "NA", "NONE", "NULL", "-", "..."} else v

def _map_libpostal_to_iso(
    components: Dict[str, Any],
    country_hint: Optional[str] = None,
    postal_code_hint: Optional[str] = None,
    town_hint: Optional[str] = None,
) -> FragmentedAddress:
    """Mapping libpostal → ISO 20022 <PstlAdr> avec correction métier"""
    
    # Nettoyage hints
    ctry = _safe_hint(country_hint)
    twn_nm = _safe_hint(town_hint)
    pst_cd = _safe_hint(postal_code_hint)
    
    # Extraction libpostal
    strt_nm = components.get("road")
    bldg_nb = components.get("house_number")
    raw_house = components.get("house") or ""
    
    # ✅ CORRECTION : Si "house" contient un mot non-résidentiel, on le mappe vers <Dept> (ctry_sub_div)
    ctry_sub_div = None
    if raw_house and any(kw in raw_house.upper() for kw in NON_RESIDENTIAL_KEYWORDS):
        ctry_sub_div = raw_house  # ISO 20022 <Dept> ou <SubDept>
    else:
        bldg_nm = raw_house
        ctry_sub_div = components.get("state") or components.get("suburb")

    room = components.get("unit") or components.get("room")
    if components.get("postcode"): pst_cd = components["postcode"]
    if components.get("city"): twn_nm = components["city"]
    if components.get("country"): ctry = components["country"]

    # Validation présence champs obligatoires ISO
    iso_fields_filled = any([strt_nm, bldg_nb, pst_cd, twn_nm, ctry_sub_div])

    if iso_fields_filled:
        return FragmentedAddress(
            strt_nm=strt_nm, bldg_nb=bldg_nb, bldg_nm=None, room=room,
            pst_cd=pst_cd, twn_nm=twn_nm, ctry_sub_div=ctry_sub_div, ctry=ctry,
            fragmentation_confidence=0.92, fallback_used=False,
        )

    # Fallback XSD garanti
    return FragmentedAddress(
        adr_line=list(components.values()) if components else [],
        pst_cd=pst_cd, twn_nm=twn_nm, ctry=ctry,
        fragmentation_confidence=0.55, fallback_used=True,
    )

def _fragment_single_line(line: str, country_hint: str = None, postal_code_hint: str = None, town_hint: str = None) -> FragmentedAddress:
    try:
        parsed = parse_address_line(line)
        if parsed.get("is_valid") and parsed.get("components"):
            return _map_libpostal_to_iso(parsed["components"], country_hint, postal_code_hint, town_hint)
    except Exception: pass
    return FragmentedAddress(adr_line=[line], pst_cd=_safe_hint(postal_code_hint), twn_nm=_safe_hint(town_hint), ctry=_safe_hint(country_hint), fragmentation_confidence=0.55, fallback_used=True)

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
        if frag.fallback_used: logger.warn(f"Fallback AdrLine: {line[:40]}...")

    party.fragmented_addresses = fragmented
    return party