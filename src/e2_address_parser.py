"""e2_address_parser.py — Parsing d'adresse via libpostal"""

from typing import Dict, List, Optional


def _normalize(text: Optional[str]) -> str:
    if not text:
        return ""
    return " ".join(text.strip().split())


def parse_address_line(address_line: str) -> Dict:
    """
    Parse une ligne d'adresse avec libpostal.
    Retourne une structure stable pour le projet.
    """
    raw = _normalize(address_line)

    if not raw:
        return {
            "raw": "",
            "parsed": [],
            "components": {},
            "is_valid": False,
            "warnings": ["empty_address_line"],
        }

    try:
        from postal.parser import parse_address
        parsed = parse_address(raw)
    except Exception as e:
        return {
            "raw": raw,
            "parsed": [],
            "components": {},
            "is_valid": False,
            "warnings": [f"libpostal_error:{type(e).__name__}"],
        }

    components: Dict[str, List[str]] = {}
    for value, label in parsed:
        value = _normalize(value)
        label = _normalize(label)
        if not value or not label:
            continue
        components.setdefault(label, []).append(value)

    flat_components = {k: " | ".join(v) for k, v in components.items()}

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
        "parsed": parsed,
        "components": flat_components,
        "is_valid": is_valid,
        "warnings": warnings,
    }
