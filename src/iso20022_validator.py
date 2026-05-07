"""iso20022_validator.py — Validateur sémantique pour les payloads ISO 20022"""

from typing import Dict, List, Any, Optional
from src.models import CanonicalParty


def validate_iso20022_semantic(party: CanonicalParty, payload: Dict[str, Any]) -> Dict[str, List[str]]:
    """
    Valide la sémantique d'un payload ISO 20022 généré depuis un CanonicalParty.
    
    Returns:
        Dict avec 'errors' et 'warnings' - listes de messages d'erreur/avertissement
    """
    errors: List[str] = []
    warnings: List[str] = []
    
    # 1. Validation du Nm (Name)
    nm = payload.get("Nm")
    if not nm:
        errors.append("Nm (Name) is mandatory and missing")
    elif not isinstance(nm, str):
        errors.append(f"Nm must be a string, got {type(nm).__name__}")
    elif len(nm) > 140:
        errors.append(f"Nm exceeds 140 characters (got {len(nm)})")
    elif len(nm.strip()) == 0:
        errors.append("Nm is empty after trimming whitespace")
    
    # 2. Validation de l'adresse postale
    pst_adr = payload.get("PstlAdr")
    if pst_adr:
        errors.extend(_validate_postal_address(pst_adr))
        warnings.extend(_validate_postal_address_warnings(pst_adr))
    
    # 3. Validation du pays de résidence
    ctry_of_res = payload.get("CtryOfRes")
    if ctry_of_res and not isinstance(ctry_of_res, str):
        errors.append(f"CtryOfRes must be a string, got {type(ctry_of_res).__name__}")
    elif ctry_of_res and len(ctry_of_res) != 2:
        errors.append(f"CtryOfRes must be a 2-letter ISO country code, got '{ctry_of_res}'")
    
    # 4. Validation des IDs
    id_payload = payload.get("Id")
    if id_payload:
        errors.extend(_validate_identification(id_payload))
    
    # 5. Cohérence entre champs
    if pst_adr and not pst_adr.get("Ctry") and not ctry_of_res:
        errors.append("Country information missing (neither PstlAdr/Ctry nor CtryOfRes present)")
    
    return {
        "errors": errors,
        "warnings": warnings
    }


def _validate_postal_address(pst_adr: Dict[str, Any]) -> List[str]:
    """Valide la structure et les valeurs de l'adresse postale."""
    errors: List[str] = []
    
    # Champs obligatoires
    if not pst_adr.get("Ctry"):
        errors.append("PstlAdr/Ctry (Country) is mandatory and missing")
    else:
        ctry = pst_adr.get("Ctry")
        if not isinstance(ctry, str) or len(ctry) != 2:
            errors.append(f"PstlAdr/Ctry must be 2-letter ISO code, got '{ctry}'")
    
    if not pst_adr.get("TwnNm"):
        errors.append("PstlAdr/TwnNm (Town) is mandatory and missing")
    else:
        twn = pst_adr.get("TwnNm")
        if not isinstance(twn, str):
            errors.append(f"PstlAdr/TwnNm must be string, got {type(twn).__name__}")
        elif len(twn) > 35:
            errors.append(f"PstlAdr/TwnNm exceeds 35 characters (got {len(twn)})")
    
    # Validation des champs structurés
    strt_nm = pst_adr.get("StrtNm")
    if strt_nm and len(str(strt_nm)) > 70:
        errors.append(f"PstlAdr/StrtNm exceeds 70 characters (got {len(strt_nm)})")
    
    bldg_nb = pst_adr.get("BldgNb")
    if bldg_nb and len(str(bldg_nb)) > 16:
        errors.append(f"PstlAdr/BldgNb exceeds 16 characters (got {len(bldg_nb)})")
    
    pst_cd = pst_adr.get("PstCd")
    if pst_cd and len(str(pst_cd)) > 16:
        errors.append(f"PstlAdr/PstCd exceeds 16 characters (got {len(pst_cd)})")
    
    # Validation du TwnLctnNm (Town Location Name) - champ optionnel mais critique
    twn_lctn = pst_adr.get("TwnLctnNm")
    if twn_lctn:
        twn_lctn_str = str(twn_lctn).strip()
        # TwnLctnNm ne doit pas être un code postal ou un numéro
        if twn_lctn_str.isdigit():
            errors.append(f"PstlAdr/TwnLctnNm appears to be numeric ('{twn_lctn_str}'), likely a postal code - this field should be a locality name")
        # TwnLctnNm ne doit pas être identique à TwnNm
        if pst_adr.get("TwnNm") and str(pst_adr.get("TwnNm")).upper() == twn_lctn_str.upper():
            errors.append(f"PstlAdr/TwnLctnNm is identical to TwnNm ('{twn_lctn_str}'), should only be present if different")
    
    # Validation des AdrLine (Address Lines)
    adr_lines = pst_adr.get("AdrLine")
    if adr_lines:
        if not isinstance(adr_lines, list):
            errors.append(f"PstlAdr/AdrLine must be a list, got {type(adr_lines).__name__}")
        else:
            for i, line in enumerate(adr_lines):
                if not isinstance(line, str):
                    errors.append(f"PstlAdr/AdrLine[{i}] must be string, got {type(line).__name__}")
                elif len(line) > 70:
                    errors.append(f"PstlAdr/AdrLine[{i}] exceeds 70 characters (got {len(line)})")
            
            # Vérification de redondance avec les champs structurés
            structured_parts = [
                pst_adr.get("StrtNm"),
                pst_adr.get("BldgNb"),
                pst_adr.get("PstCd"),
                pst_adr.get("TwnNm"),
            ]
            for i, line in enumerate(adr_lines):
                line_upper = str(line).upper()
                for part in structured_parts:
                    if part and str(part).upper() in line_upper:
                        # C'est normal que les AdrLine répètent parfois les champs structurés
                        pass
    
    return errors


def _validate_postal_address_warnings(pst_adr: Dict[str, Any]) -> List[str]:
    """Génère des avertissements pour les pratiques douteuses."""
    warnings: List[str] = []
    
    # Avertissement: AdrLine avec adresse structurée
    structured = any([pst_adr.get(k) for k in ["StrtNm", "BldgNb", "BldgNm", "PstBx", "Room"]])
    adr_lines = pst_adr.get("AdrLine") or []
    if structured and adr_lines:
        warnings.append(f"PstlAdr has both structured fields (StrtNm/BldgNb/etc) and AdrLine ({len(adr_lines)} lines) - mixing structured and unstructured addressing")
    
    # Avertissement: Pas d'adresse physique
    if not structured and not adr_lines:
        warnings.append("PstlAdr has only country and town, no street/building/address details")
    
    # Avertissement: Postal Code manquant
    if not pst_adr.get("PstCd"):
        warnings.append("PstlAdr/PstCd (Postal Code) is missing")
    
    return warnings


def _validate_identification(id_payload: Dict[str, Any]) -> List[str]:
    """Valide la structure des identifiants."""
    errors: List[str] = []
    
    org_id = id_payload.get("OrgId")
    prvt_id = id_payload.get("PrvtId")
    
    if not org_id and not prvt_id:
        errors.append("Id present but neither OrgId nor PrvtId found")
        return errors
    
    # Validation OrgId
    if org_id:
        org_othr = org_id.get("Othr", [])
        if not org_othr:
            # OrgId peut être vide si on a d'autres champs, mais généralement on veut Othr
            pass
        elif not isinstance(org_othr, list):
            errors.append(f"OrgId/Othr must be a list, got {type(org_othr).__name__}")
    
    # Validation PrvtId
    if prvt_id:
        prvt_othr = prvt_id.get("Othr", [])
        dob_info = prvt_id.get("DtAndPlcOfBirth")
        if not prvt_othr and not dob_info:
            errors.append("PrvtId present but neither Othr nor DtAndPlcOfBirth found")
    
    return errors


def suggest_iso20022_fixes(party: CanonicalParty, payload: Dict[str, Any]) -> List[str]:
    """Suggère des corrections basées sur les erreurs détectées."""
    suggestions: List[str] = []
    validation_result = validate_iso20022_semantic(party, payload)
    errors = validation_result.get("errors", [])
    
    for error in errors:
        if "TwnLctnNm appears to be numeric" in error:
            suggestions.append("Remove TwnLctnNm field or fill with actual locality name instead of postal code")
        elif "TwnLctnNm is identical to TwnNm" in error:
            suggestions.append("Remove duplicate TwnLctnNm field - it should differ from TwnNm if present")
        elif "Nm is empty" in error:
            suggestions.append("Ensure party name is populated before generating ISO 20022 message")
        elif "Country information missing" in error:
            suggestions.append("Fill country code in either PstlAdr/Ctry or CtryOfRes")
    
    return suggestions
