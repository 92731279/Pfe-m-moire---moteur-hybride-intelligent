"""Mapping CanonicalParty -> structure ISO 20022 et XML well-formed."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

from src.models import CanonicalParty, FragmentedAddress, PartyIdentifier


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
    geo = party.country_town
    address_lines = _clean_list(party.address_lines)
    postal_complement = _clean_text(getattr(party, "postal_complement", None))
    original_town = _extract_original_structured_town(party)
    canonical_town = _clean_text(getattr(fragment, "twn_nm", None) or (geo.town if geo else None))

    if postal_complement and postal_complement not in address_lines:
        address_lines.append(postal_complement)

    strt_nm = _clean_text(getattr(fragment, "strt_nm", None))
    bldg_nb = _clean_text(getattr(fragment, "bldg_nb", None))
    bldg_nm = _clean_text(getattr(fragment, "bldg_nm", None))
    flr = _clean_text(getattr(fragment, "flr", None))
    pst_bx = postal_complement or _detect_post_box(address_lines)
    room = _clean_text(getattr(fragment, "room", None))
    pst_cd = _clean_text(getattr(fragment, "pst_cd", None) or (geo.postal_code if geo else None))
    ctry_sub_div = _clean_text(getattr(fragment, "ctry_sub_div", None))
    ctry = _clean_text(getattr(fragment, "ctry", None) or (geo.country if geo else None))

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
        "TwnLctnNm": (
            _clean_text(original_town)
            if original_town and canonical_town and _cmp_norm(original_town) != _cmp_norm(canonical_town)
            else None
        ),
        "DstrctNm": None,
        "CtrySubDvsn": ctry_sub_div,
        "Ctry": ctry,
        "AdrLine": filtered_address_lines,
    }

    return {key: value for key, value in postal_address.items() if value not in (None, [], "")}


def _build_organisation_identification(party: CanonicalParty) -> Optional[Dict[str, Any]]:
    candidates = [party.org_id, party.party_id]
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
        (
            getattr(party.party_id, "identifier", None),
            getattr(party.party_id, "code", None),
            getattr(party.party_id, "issuer", None) or getattr(party.party_id, "country", None),
        ),
    ]
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
