"""Mapping CanonicalParty -> structure ISO 20022 et XML well-formed."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

from src.models import CanonicalParty, FragmentedAddress, PartyIdentifier

PRIVATE_PARTY_ID_CODES = {"ARNU", "CCPT", "NIDN", "SOSE", "TXID"}
ORGANISATION_PARTY_ID_CODES = {"CUST", "DRLC", "EMPL"}


def _clean_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = " ".join(str(value).strip().split())
    return cleaned or None


def _clean_list(values: List[str]) -> List[str]:
    result: List[str] = []
    for value in values or []:
        cleaned = _clean_text(value)
        if cleaned:
            result.append(cleaned)
    return result


def _cmp_norm(value: Optional[str]) -> str:
    if not value:
        return ""
    normalized = _clean_text(value) or ""
    normalized = re.sub(r"[^A-Z0-9]+", " ", normalized.upper())
    return " ".join(normalized.split())


def _best_fragment(party: CanonicalParty) -> Optional[FragmentedAddress]:
    fragments = getattr(party, "fragmented_addresses", []) or []
    if not fragments:
        return None
    return max(fragments, key=lambda frag: getattr(frag, "fragmentation_confidence", 0.0) or 0.0)


def _best_street_fragment(party: CanonicalParty) -> Optional[FragmentedAddress]:
    fragments = list(getattr(party, "fragmented_addresses", []) or [])
    if not fragments:
        return None

    candidates = [frag for frag in fragments if getattr(frag, "strt_nm", None) or getattr(frag, "bldg_nb", None) or getattr(frag, "bldg_nm", None) or getattr(frag, "room", None)]
    if not candidates:
        return None

    def _score(frag: FragmentedAddress) -> float:
        score = 0.0
        if getattr(frag, "strt_nm", None):
            score += 4.0
        if getattr(frag, "bldg_nb", None):
            score += 2.0
        if getattr(frag, "bldg_nm", None):
            score += 1.5
        if getattr(frag, "room", None):
            score += 1.0
        score += float(getattr(frag, "fragmentation_confidence", 0.0) or 0.0)
        return score

    return max(candidates, key=_score)


def _best_geo_fragment(party: CanonicalParty) -> Optional[FragmentedAddress]:
    fragments = list(getattr(party, "fragmented_addresses", []) or [])
    if not fragments:
        return None

    candidates = [frag for frag in fragments if getattr(frag, "twn_nm", None) or getattr(frag, "pst_cd", None)]
    if not candidates:
        return None

    def _score(frag: FragmentedAddress) -> float:
        score = 0.0
        if getattr(frag, "twn_nm", None):
            score += 4.0
        if getattr(frag, "pst_cd", None):
            score += 3.0
        if getattr(frag, "ctry_sub_div", None):
            score += 1.0
        if getattr(frag, "strt_nm", None):
            score -= 1.0
        score += float(getattr(frag, "fragmentation_confidence", 0.0) or 0.0)
        return score

    return max(candidates, key=_score)


def _detect_post_box(lines: List[str]) -> Optional[str]:
    for line in lines or []:
        upper = line.upper()
        match = re.search(r"\b(?:BP|B\.P\.|PO BOX|P\.O\. BOX)\s*([A-Z0-9-]+(?:\s+[A-Z0-9-]+)?)", upper)
        if match:
            return _clean_text(match.group(0))
    return None


def _extract_original_structured_town(party: CanonicalParty) -> Optional[str]:
    raw = getattr(party, "raw", None)
    if not raw:
        return None

    for line in str(raw).splitlines():
        normalized = _clean_text(line)
        if not normalized or not normalized.startswith("3/"):
            continue
        parts = [part.strip() for part in normalized.split("/")]
        if len(parts) < 3:
            continue
        candidate = _clean_text(parts[-1])
        if candidate:
            candidate = re.sub(r"^\d{3,10}\s+", "", candidate).strip()
            return candidate
    return None


def _extract_structured_line3_details(party: CanonicalParty) -> Dict[str, Optional[str]]:
    details: Dict[str, Optional[str]] = {
        "country": None,
        "locality_raw": None,
        "town_candidate": None,
        "postal_candidate": None,
        "sub_div_candidate": None,
    }

    raw = getattr(party, "raw", None)
    if not raw:
        return details

    for line in str(raw).splitlines():
        normalized = _clean_text(line)
        if not normalized or not normalized.startswith("3/"):
            continue

        parts = [part.strip() for part in normalized.split("/", 2)]
        if len(parts) < 3:
            continue

        country = _clean_text(parts[1])
        locality = _clean_text(parts[2])
        if not locality:
            continue

        details["country"] = country
        details["locality_raw"] = locality

        candidate = locality
        postal_candidate = None
        sub_div_candidate = None

        # Works for ZIP, alphanumeric postcodes, and spaced formats (e.g. M5H 2N2).
        postal_patterns = [
            r"\b(\d{5}(?:-\d{4})?)$",  # US ZIP / ZIP+4
            r"\b([ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z][ -]?\d[ABCEGHJ-NPRSTV-Z]\d)$",  # Canada
            r"\b([A-Z0-9]{3,10})$",  # Generic compact postal
        ]
        for pattern in postal_patterns:
            m_postal = re.search(pattern, candidate.upper())
            if not m_postal:
                continue
            extracted = _clean_text(m_postal.group(1))
            if not extracted or not re.search(r"\d", extracted):
                continue
            postal_candidate = extracted
            candidate = candidate[:m_postal.start()].rstrip(" ,-")
            break

        m_sub = re.search(r"^(.*?)(?:,\s*|\s+)([A-Z]{2,3})$", candidate.upper())
        if m_sub and len((m_sub.group(1) or "").split()) >= 1:
            sub_div_candidate = _clean_text(m_sub.group(2))
            candidate = candidate[:len(m_sub.group(1))].rstrip(" ,-")

        details["town_candidate"] = _clean_text(candidate)
        details["postal_candidate"] = postal_candidate
        details["sub_div_candidate"] = sub_div_candidate
        return details

    return details


def _is_redundant_locality(locality: Optional[str], town: Optional[str], sub_div: Optional[str], postal: Optional[str]) -> bool:
    if not locality or not town:
        return False

    locality_n = _cmp_norm(locality)
    town_n = _cmp_norm(town)
    sub_div_n = _cmp_norm(sub_div)
    postal_n = _cmp_norm(postal)

    if locality_n == town_n:
        return True

    tokens = set(locality_n.split())
    if not town_n or not set(town_n.split()).issubset(tokens):
        return False

    if sub_div_n and set(sub_div_n.split()).issubset(tokens):
        pass
    elif sub_div_n:
        return False

    if postal_n and set(postal_n.split()).issubset(tokens):
        pass
    elif postal_n:
        return False

    # If locality only repeats already-mapped components (town/subdivision/postal), skip it.
    composite = " ".join(part for part in [town_n, sub_div_n, postal_n] if part).strip()
    return bool(composite and locality_n == composite)


def _scheme_name_from_identifier(identifier: Optional[PartyIdentifier], default_code: str = "CUST") -> Optional[Dict[str, str]]:
    if not identifier:
        return {"Cd": default_code}
    if identifier.code:
        return {"Cd": _clean_text(identifier.code)}
    return {"Cd": default_code}


def _build_other_block(identifier: Optional[str], scheme_code: Optional[str], issuer: Optional[str]) -> Optional[Dict[str, Any]]:
    identifier = _clean_text(identifier)
    if not identifier:
        return None

    payload: Dict[str, Any] = {"Id": identifier}
    if scheme_code:
        payload["SchmeNm"] = {"Cd": _clean_text(scheme_code)}
    if issuer:
        payload["Issr"] = _clean_text(issuer)
    return payload


def _build_postal_address(party: CanonicalParty) -> Dict[str, Any]:
    fragment = _best_fragment(party)
    street_fragment = _best_street_fragment(party) or fragment
    geo_fragment = _best_geo_fragment(party) or fragment
    geo = party.country_town
    address_lines = _clean_list(party.address_lines)
    postal_complement = _clean_text(getattr(party, "postal_complement", None))
    original_town = _extract_original_structured_town(party)
    line3_details = _extract_structured_line3_details(party)
    canonical_town = _clean_text(getattr(geo_fragment, "twn_nm", None) or (geo.town if geo else None))

    if postal_complement and postal_complement not in address_lines:
        address_lines.append(postal_complement)

    strt_nm = _clean_text(getattr(street_fragment, "strt_nm", None))
    bldg_nb = _clean_text(getattr(street_fragment, "bldg_nb", None))
    bldg_nm = _clean_text(getattr(street_fragment, "bldg_nm", None))
    flr = _clean_text(getattr(street_fragment, "flr", None))
    pst_bx = postal_complement or _detect_post_box(address_lines)
    room = _clean_text(getattr(street_fragment, "room", None))
    pst_cd = _clean_text(
        getattr(geo_fragment, "pst_cd", None)
        or (geo.postal_code if geo else None)
        or line3_details.get("postal_candidate")
    )
    ctry_sub_div = _clean_text(
        getattr(geo_fragment, "ctry_sub_div", None)
        or getattr(street_fragment, "ctry_sub_div", None)
        or line3_details.get("sub_div_candidate")
    )
    ctry = _clean_text(getattr(geo_fragment, "ctry", None) or getattr(street_fragment, "ctry", None) or (geo.country if geo else None))

    locality_fragment = None
    for candidate in getattr(party, "fragmented_addresses", []) or []:
        cand_town = _clean_text(getattr(candidate, "twn_nm", None))
        if not cand_town or not canonical_town:
            continue
        if _cmp_norm(cand_town) == _cmp_norm(canonical_town):
            continue
        locality_fragment = cand_town
        break

    redundant_lines: set[str] = set()
    for value in [strt_nm, bldg_nm, flr, pst_bx, room, pst_cd, canonical_town, original_town, ctry_sub_div, ctry]:
        cleaned = _clean_text(value)
        if cleaned:
            redundant_lines.add(_cmp_norm(cleaned))

    structured_variants = [
        _clean_text(" ".join(part for part in [bldg_nb, strt_nm] if part)),
        _clean_text(" ".join(part for part in [strt_nm, bldg_nb] if part)),
        _clean_text(" ".join(part for part in [bldg_nb, strt_nm, room] if part)),
        _clean_text(" ".join(part for part in [strt_nm, bldg_nb, room] if part)),
        _clean_text(" ".join(part for part in [strt_nm, bldg_nm] if part)),
        _clean_text(" ".join(part for part in [strt_nm, bldg_nb, bldg_nm] if part)),
        _clean_text(" ".join(part for part in [canonical_town, ctry_sub_div, pst_cd] if part)),
        _clean_text(" ".join(part for part in [canonical_town, pst_cd] if part)),
        _clean_text(" ".join(part for part in [ctry_sub_div, pst_cd] if part)),
    ]
    structured_variants = [variant for variant in structured_variants if variant]
    for variant in structured_variants:
        redundant_lines.add(_cmp_norm(variant))

    filtered_address_lines: List[str] = []
    for line in address_lines if address_lines else _clean_list(getattr(fragment, "adr_line", None) or []):
        line_norm = _cmp_norm(line)
        if line_norm in redundant_lines:
            continue
        filtered_address_lines.append(line)

    inferred_locality = (
        locality_fragment
        or (
            _clean_text(line3_details.get("locality_raw"))
            if line3_details.get("locality_raw") and canonical_town
            else _clean_text(original_town)
        )
    )
    if _is_redundant_locality(inferred_locality, canonical_town, ctry_sub_div, pst_cd):
        inferred_locality = None

    postal_address: Dict[str, Any] = {
        "AdrTp": None,
        "Dept": None,
        "SubDept": None,
        "StrtNm": strt_nm,
        "BldgNb": bldg_nb,
        "BldgNm": bldg_nm,
        "Flr": flr,
        "PstBx": pst_bx,
        "Room": room,
        "PstCd": pst_cd,
        "TwnNm": canonical_town,
        "TwnLctnNm": inferred_locality,
        "DstrctNm": None,
        "CtrySubDvsn": ctry_sub_div,
        "Ctry": ctry,
        "AdrLine": filtered_address_lines,
    }

    return {key: value for key, value in postal_address.items() if value not in (None, [], "")}


def _build_organisation_identification(party: CanonicalParty) -> Optional[Dict[str, Any]]:
    candidates = [party.org_id]
    if party.is_org is True and party.party_id and getattr(party.party_id, "code", None) in ORGANISATION_PARTY_ID_CODES:
        candidates.append(party.party_id)
    other_entries: List[Dict[str, Any]] = []

    for candidate in candidates:
        block = _build_other_block(
            identifier=getattr(candidate, "identifier", None),
            scheme_code=(getattr(candidate, "code", None) or "CUST"),
            issuer=getattr(candidate, "issuer", None) or getattr(candidate, "country", None),
        )
        if block and block not in other_entries:
            other_entries.append(block)

    if not other_entries:
        return None

    return {"Othr": other_entries}


def _build_private_identification(party: CanonicalParty) -> Optional[Dict[str, Any]]:
    payload: Dict[str, Any] = {}

    other_entries: List[Dict[str, Any]] = []
    private_candidates: List[Tuple[Optional[str], Optional[str], Optional[str]]] = [
        (
            party.national_id,
            getattr(party.party_id, "code", None) or "NIDN",
            getattr(party.party_id, "issuer", None) or getattr(party.party_id, "country", None),
        ),
    ]
    party_id_code = getattr(party.party_id, "code", None)
    if party.party_id and (party.is_org is not True or party_id_code in PRIVATE_PARTY_ID_CODES):
        private_candidates.append(
            (
                getattr(party.party_id, "identifier", None),
                getattr(party.party_id, "code", None),
                getattr(party.party_id, "issuer", None) or getattr(party.party_id, "country", None),
            )
        )
    for identifier, scheme_code, issuer in private_candidates:
        block = _build_other_block(identifier, scheme_code, issuer)
        if block and block not in other_entries:
            other_entries.append(block)

    if other_entries:
        payload["Othr"] = other_entries

    birth_date = None
    if party.dob and party.dob.year and party.dob.month and party.dob.day:
        birth_date = f"{party.dob.year}-{party.dob.month}-{party.dob.day}"
    elif party.dob and party.dob.raw and re.fullmatch(r"\d{8}", party.dob.raw):
        birth_date = f"{party.dob.raw[:4]}-{party.dob.raw[4:6]}-{party.dob.raw[6:8]}"

    city_of_birth = _clean_text(party.pob.city if party.pob else None)
    country_of_birth = _clean_text(party.pob.country if party.pob else None)
    if birth_date or city_of_birth or country_of_birth:
        payload["DtAndPlcOfBirth"] = {
            key: value
            for key, value in {
                "BirthDt": birth_date,
                "PrvcOfBirth": None,
                "CityOfBirth": city_of_birth,
                "CtryOfBirth": country_of_birth,
            }.items()
            if value not in (None, "")
        }

    return payload or None


def build_iso20022_party_payload(party: CanonicalParty) -> Dict[str, Any]:
    name = _clean_text(" ".join(party.name))
    postal_address = _build_postal_address(party)
    country_of_residence = _clean_text(party.country_town.country if party.country_town else None)

    payload: Dict[str, Any] = {}
    if name:
        payload["Nm"] = name
    if postal_address:
        payload["PstlAdr"] = postal_address

    organisation_id = _build_organisation_identification(party)
    private_id = _build_private_identification(party)
    id_payload: Dict[str, Any] = {}
    if party.is_org is True:
        if organisation_id:
            id_payload["OrgId"] = organisation_id
        if private_id:
            id_payload["PrvtId"] = private_id
    elif party.is_org is False:
        if private_id:
            id_payload["PrvtId"] = private_id
        if organisation_id:
            id_payload["OrgId"] = organisation_id
    else:
        if organisation_id:
            id_payload["OrgId"] = organisation_id
        if private_id:
            id_payload["PrvtId"] = private_id

    if id_payload:
        payload["Id"] = id_payload
    if country_of_residence:
        payload["CtryOfRes"] = country_of_residence

    return payload


def _append_xml(parent: Element, key: str, value: Any) -> None:
    if value in (None, "", []):
        return

    if isinstance(value, list):
        for item in value:
            child = SubElement(parent, key)
            if isinstance(item, (dict, list)):
                if isinstance(item, dict):
                    for sub_key, sub_val in item.items():
                        _append_xml(child, sub_key, sub_val)
            else:
                child.text = str(item)
        return

    child = SubElement(parent, key)
    if isinstance(value, dict):
        for sub_key, sub_val in value.items():
            _append_xml(child, sub_key, sub_val)
    else:
        child.text = str(value)


def validate_iso20022_party_payload(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []

    if not payload.get("Nm"):
        errors.append("missing Nm")

    postal_address = payload.get("PstlAdr") or {}
    if postal_address and not postal_address.get("Ctry"):
        errors.append("missing PstlAdr/Ctry")
    if postal_address and not postal_address.get("TwnNm"):
        errors.append("missing PstlAdr/TwnNm")

    if payload.get("Id"):
        id_payload = payload["Id"]
        org_others = (((id_payload.get("OrgId") or {}).get("Othr")) or [])
        prvt_others = (((id_payload.get("PrvtId") or {}).get("Othr")) or [])
        if not org_others and not prvt_others and not ((id_payload.get("PrvtId") or {}).get("DtAndPlcOfBirth")):
            errors.append("Id present without usable OrgId/PrvtId payload")

    return errors


def build_iso20022_party_xml(
    party: CanonicalParty,
    role_tag: Optional[str] = None,
    include_envelope: bool = False,
) -> Tuple[str, Dict[str, Any], List[str]]:
    payload = build_iso20022_party_payload(party)
    errors = validate_iso20022_party_payload(payload)

    role = role_tag or ("Dbtr" if party.role == "debtor" else "Cdtr")

    if include_envelope:
        root = Element("Document")
        fitofi = SubElement(root, "FIToFICstmrCdtTrf")
        tx = SubElement(fitofi, "CdtTrfTxInf")
        role_node = SubElement(tx, role)
    else:
        root = Element(role)
        role_node = root

    for key, value in payload.items():
        _append_xml(role_node, key, value)

    xml_bytes = tostring(root, encoding="utf-8")
    xml_pretty = minidom.parseString(xml_bytes).toprettyxml(indent="  ")
    return xml_pretty, payload, errors
