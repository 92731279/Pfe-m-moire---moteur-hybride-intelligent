"""
postal_slm_fallback.py — Fallback SLM pour inférence code postal → ville
Utilisé quand le dictionnaire postal_mappings.json n'a pas la réponse.
"""

import json
import logging
from typing import Optional
from src.config import OLLAMA_BASE_URL, OLLAMA_TIMEOUT_SECONDS, OLLAMA_MAX_RETRIES, get_ollama_base_urls
from src.geonames.geonames_db import infer_city_with_slm_candidate_info
from src.slm_validation import validate_slm_town

logger = logging.getLogger(__name__)


def infer_city_via_slm_postal(country_code: str, postal_code: str, model: str = "phi3:mini") -> Optional[str]:
    """
    Fallback SLM pour déduire la ville depuis code postal + pays.
    
    Utilisé quand:
    1. Le dictionnaire postal_mappings.json n'a pas l'entrée
    2. On a un code postal ET un pays valides
    3. On veut utiliser le SLM pour faire une meilleure déduction
    
    Processus:
    1. Récupérer les villes principales du pays (contexte GeoNames)
    2. Construire un prompt SLM structuré
    3. Interroger le LLM pour obtenir la ville la plus probable
    4. Parser la réponse et valider
    
    Args:
        country_code: Code pays ISO 2 lettres (ex: "TN", "FR", "US")
        postal_code: Code postal (ex: "1000", "75001", "E14 5AB")
        model: Modèle Ollama à utiliser (default: "phi3:mini")
    
    Returns:
        Nom de la ville inféré, ou None si échec
    
    Exemples:
        - infer_city_via_slm_postal("TN", "8000") → "NABEUL"
        - infer_city_via_slm_postal("FR", "13000") → "MARSEILLE"
        - infer_city_via_slm_postal("GB", "E14 5AB") → "LONDON"
    """
    if not country_code or not postal_code:
        return None
    
    country_code = country_code.upper().strip()
    postal_code = postal_code.strip()
    
    # Étape 1: Récupérer les données candidates GeoNames
    candidate_info = infer_city_with_slm_candidate_info(country_code, postal_code)
    if not candidate_info or not candidate_info.get("major_cities"):
        logger.debug(f"[SLM POSTAL] Pas de villes trouvées pour {country_code}")
        return None
    
    major_cities = candidate_info["major_cities"]
    
    # Étape 2: Construire le prompt SLM
    city_list = "\n".join([
        f"  - {city['name']} (population: {city.get('population', 'unknown')})"
        for city in major_cities[:10]
    ])
    
    prompt = f"""Given the postal code "{postal_code}" in country "{country_code}", 
identify the city name from the candidate list below.

Major cities in {country_code}:
{city_list}

Return ONLY the city name (no explanation, no formatting):"""
    
    # Étape 3: Interroger le LLM
    try:
        import requests

        response = None
        last_error = None
        for base_url in get_ollama_base_urls():
            try:
                response = requests.post(
                    f"{base_url}/api/generate",
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "temperature": 0.1,  # Low temperature for deterministic output
                    },
                    timeout=OLLAMA_TIMEOUT_SECONDS,
                )
                response.raise_for_status()
                break
            except requests.ConnectionError as e:
                last_error = e
                logger.warning(f"[SLM POSTAL] Connexion impossible via {base_url}: {e}")
                response = None
                continue

        if response is None:
            raise last_error or ConnectionError("Aucun endpoint Ollama disponible")
        
        result = response.json()
        llm_output = result.get("response", "").strip()
        
        # Étape 4: Parser la réponse
        if not llm_output:
            return None
        
        # Nettoyer la réponse (première ligne, majuscules, etc.)
        city_candidate = llm_output.split("\n")[0].strip().upper()
        
        # Valider que la réponse est dans la liste des candidats
        valid_cities = {city["name"].upper(): city["name"] for city in major_cities}
        if city_candidate in valid_cities:
            inferred_city = valid_cities[city_candidate]
            validated_city, validation_reason = validate_slm_town(country_code, inferred_city, postal_code)
            if validated_city:
                logger.info(f"[SLM POSTAL] ✅ {country_code}/{postal_code} → {validated_city} ({validation_reason})")
                return validated_city
            logger.warning(
                f"[SLM POSTAL] ⚠️  Ville SLM rejetée après validation backend: {inferred_city} ({validation_reason})"
            )
            return None
        
        # Fallback: chercher un match partiel si exact fail
        for valid_name in valid_cities.keys():
            if city_candidate in valid_name or valid_name in city_candidate:
                inferred_city = valid_cities[valid_name]
                validated_city, validation_reason = validate_slm_town(country_code, inferred_city, postal_code)
                if validated_city:
                    logger.info(f"[SLM POSTAL] ✅ (partial match) {country_code}/{postal_code} → {validated_city} ({validation_reason})")
                    return validated_city
                logger.warning(
                    f"[SLM POSTAL] ⚠️  Partial match rejeté par validation backend: {inferred_city} ({validation_reason})"
                )
                return None
        
        logger.warning(f"[SLM POSTAL] ⚠️  Response not in candidates: {city_candidate}")
        return None
        
    except Exception as e:
        logger.error(f"[SLM POSTAL] ❌ Erreur SLM pour {country_code}/{postal_code}: {e}")
        return None


def needs_postal_slm_fallback(country_code: Optional[str], postal_code: Optional[str], 
                             town: Optional[str]) -> bool:
    """
    Décide si on doit utiliser le fallback SLM pour inférence postal.
    
    Conditions:
    1. On a un pays ET un code postal valides
    2. La ville est absente ou invalide
    
    Args:
        country_code: Code pays
        postal_code: Code postal
        town: Ville trouvée (ou None)
    
    Returns:
        True si SLM postal fallback doit être utilisé
    """
    return (
        country_code and 
        postal_code and 
        (not town or str(town).strip().upper() in ["", "NONE", "N/A", "NULL"])
    )
