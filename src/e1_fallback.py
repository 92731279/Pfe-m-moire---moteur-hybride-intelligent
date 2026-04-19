"""e1_fallback.py — Fallback universel quand E1 échoue
Utilise Libpostal + GeoNames pour extraire ville/pays de n'importe quelle ligne
"""
import re
from typing import Optional, Tuple
from src.models import CountryTown
from src.reference_data import COUNTRY_CODES, resolve_country_code

try:
    from postal.parser import parse_address
    LIBPOSTAL_AVAILABLE = True
except ImportError:
    LIBPOSTAL_AVAILABLE = False

try:
    from src.geonames.geonames_validator import validate_town_in_country
    GEONAMES_AVAILABLE = True
except ImportError:
    GEONAMES_AVAILABLE = False

def _normalize(text: Optional[str]) -> str:
    if not text: return ""
    return " ".join(text.strip().upper().split())

def extract_geo_from_line_with_libpostal(line: str, iban_country: Optional[str] = None) -> Optional[CountryTown]:
    """
    Utilise Libpostal pour parser n'importe quelle ligne d'adresse.
    Extrait country/city/postcode même si format inconnu.
    """
    if not LIBPOSTAL_AVAILABLE or not line.strip():
        return None
    
    try:
        parsed = parse_address(_normalize(line))
        components = {label.upper(): value for value, label in parsed}
        
        # Extraire les composants
        country_code = components.get("COUNTRY")
        city = components.get("CITY")
        postcode = components.get("POSTCODE")
        state = components.get("STATE")
        
        # Résoudre le code pays
        country = None
        if country_code:
            country = resolve_country_code(country_code)
        elif iban_country:
            country = iban_country
        
        # Si on a au moins un élément géographique
        if country or city or postcode:
            # Validation GeoNames si disponible
            if GEONAMES_AVAILABLE and city and country:
                is_valid, canonical, _ = validate_town_in_country(country, city)
                if is_valid:
                    city = canonical
            
            return CountryTown(
                country=country or iban_country,
                town=city,
                postal_code=postcode
            )
    except Exception as e:
        pass
    
    return None

def extract_geo_from_address_lines(address_lines: list, iban_country: Optional[str] = None) -> Optional[CountryTown]:
    """
    Tente d'extraire des infos géo de chaque ligne d'adresse.
    Retourne la première ville valide trouvée.
    """
    for line in address_lines:
        # Essayer Libpostal
        geo = extract_geo_from_line_with_libpostal(line, iban_country)
        if geo and (geo.town or geo.postal_code):
            return geo
        
        # Fallback: chercher un pattern postal simple
        m = re.search(r'\b(\d{4,6})\s+([A-Z][A-Z\s]+)\b', _normalize(line))
        if m:
            postcode = m.group(1)
            town_candidate = m.group(2).strip()
            # Valider avec GeoNames si possible
            if GEONAMES_AVAILABLE and iban_country:
                is_valid, canonical, _ = validate_town_in_country(iban_country, town_candidate)
                if is_valid:
                    return CountryTown(country=iban_country, town=canonical, postal_code=postcode)
            else:
                return CountryTown(country=iban_country, town=town_candidate, postal_code=postcode)
    
    return None