"""src/e2_address_parser.py — Parsing d'adresse via libpostal + Correction sémantique métier"""
from typing import Dict, List, Optional

def _normalize_label(text: Optional[str]) -> str:
    """Normalise les labels libpostal (road, house, suburb...)"""
    if not text: return ""
    return "".join(text.strip().upper().split())

def _normalize_value(text: Optional[str]) -> str:
    """Normalise les valeurs en conservant les espaces internes pour la lisibilité et le matching"""
    if not text: return ""
    return " ".join(text.strip().upper().split())

def parse_address_line(address_line: str) -> Dict:
    """
    Parse une ligne d'adresse avec libpostal.
    CORRECTION MÉTIER : 
    - Si libpostal retourne 'house' mais que le texte contient ZONE/CITE/INDUSTRIELLE,
      on reclassifie automatiquement en 'suburb' (zone administrative/commerciale).
    - Cela permet un mapping ISO 20022 correct vers <Dept> ou <CtrySubDvsn>.
    """
    raw = address_line.strip().upper()
    if not raw:
        return {
            "raw": "", "parsed": [], "components": {},
            "is_valid": False, "warnings": ["empty_address_line"],
        }

    try:
        from postal.parser import parse_address
        parsed = parse_address(raw)
    except Exception as e:
        return {
            "raw": raw, "parsed": [], "components": {},
            "is_valid": False, "warnings": [f"libpostal_error:{type(e).__name__}"],
        }

    # 🛡️ CORRECTION SÉMANTIQUE : Reclassification avant normalisation
    NON_HOUSE_KEYWORDS = {"ZONE", "CITE", "CITÉ", "QUARTIER", "SECTEUR", "INDUSTRIELLE", 
                          "INDUSTRIAL", "COMMERCIAL", "IMMEUBLE", "IMM", "BLOC", "PARC"}
    
    corrected_parsed = []
    for value, label in parsed:
        val_upper = value.upper()
        # Si c'est classé 'house' mais contient un mot-clé zone/commerce → on passe en 'suburb'
        if label == "house" and any(kw in val_upper for kw in NON_HOUSE_KEYWORDS):
            corrected_parsed.append((value, "suburb"))
        else:
            corrected_parsed.append((value, label))

    # Construction du dictionnaire de composants
    components: Dict[str, List[str]] = {}
    for value, label in corrected_parsed:
        label_norm = _normalize_label(label)
        value_norm = _normalize_value(value)
        if not value_norm or not label_norm:
            continue
        components.setdefault(label_norm, []).append(value_norm)

    # Aplatir pour l'affichage/debug
    flat_components = {k: " | ".join(v) for k, v in components.items()}

    # Validation basique
    key_labels = {"road", "house_number", "unit", "postcode", "city", "suburb", "state", "country"}
    found_key_labels = set(flat_components.keys()) & key_labels
    is_valid = len(found_key_labels) > 0

    warnings: List[str] = []
    if not parsed:
        warnings.append("no_components_detected")
    if "road" not in flat_components and "house_number" not in flat_components:
        warnings.append("missing_road_like_component")

    return {
        "raw": raw,
        "parsed": corrected_parsed,
        "components": flat_components,
        "is_valid": is_valid,
        "warnings": warnings,
    }