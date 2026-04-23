# =============================================================================
# e3_slm_fallback.py - VERSION CORRIGÉE ET OPTIMISÉE
# Fallback SLM (Small Language Model) pour cas ambigus
# OPTIMISATIONS: Cache, timeout court, prompt structuré, format clé:valeur
# =============================================================================

import re
import json
import logging
import hashlib
import time
from typing import Optional, Dict, Any, List
import requests
from src.config import OLLAMA_BASE_URL, OLLAMA_TIMEOUT_SECONDS, OLLAMA_MAX_RETRIES
from src.models import CanonicalParty, CountryTown
from src.reference_data import resolve_country_code

logger = logging.getLogger(__name__)


# =============================================================================
# CIRCUIT BREAKER SIMPLE - Éviter les cascades d'erreurs Ollama
# =============================================================================

class OllamaCircuitBreaker:
    """Circuit breaker simple pour protéger contre les surcharges Ollama."""
    
    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 30):
        self.failure_threshold = failure_threshold  # Nombre d'erreurs avant de ouvrir
        self.recovery_timeout = recovery_timeout    # Secondes avant retry après fermeture
        self.failure_count = 0
        self.last_failure_time = None
        self.is_open = False
    
    def record_failure(self):
        """Enregistre une failure."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            logger.warning(
                f"[E3] Circuit breaker OUVERT après {self.failure_count} erreurs. "
                f"Retentatives bloquées pour {self.recovery_timeout}s"
            )
    
    def record_success(self):
        """Réinitialise après succès."""
        self.failure_count = 0
        self.last_failure_time = None
        self.is_open = False
    
    def can_attempt(self) -> bool:
        """Vérifie si une tentative est possible."""
        if not self.is_open:
            return True
        
        # Vérifier si le timeout de récupération est passé
        if self.last_failure_time and (time.time() - self.last_failure_time) > self.recovery_timeout:
            logger.info("[E3] Circuit breaker tentative de FERMETURE")
            self.is_open = False
            self.failure_count = 0
            return True
        
        return False


_ollama_circuit_breaker = OllamaCircuitBreaker(failure_threshold=2, recovery_timeout=20)


def _meta_get(meta: Any, field: str, default: Any = None) -> Any:
    """Compat helper for CanonicalMeta instances and legacy dict metadata."""
    if meta is None:
        return default
    if isinstance(meta, dict):
        return meta.get(field, default)
    return getattr(meta, field, default)


def _meta_set(meta: Any, field: str, value: Any) -> None:
    """Compat helper for CanonicalMeta instances and legacy dict metadata."""
    if meta is None:
        return
    if isinstance(meta, dict):
        meta[field] = value
    else:
        setattr(meta, field, value)


def _looks_like_account_or_iban(value: Optional[str]) -> bool:
    if not value:
        return False
    normalized = re.sub(r"[\s()/:-]+", "", value.upper())
    if not normalized:
        return False
    return bool(re.fullmatch(r"[A-Z]{2}\d{10,34}", normalized))


def _contains_account_text(value: Optional[str], account: Optional[str]) -> bool:
    if not value or not account:
        return False
    left = re.sub(r"[\s()/:-]+", "", value.upper())
    right = re.sub(r"[\s()/:-]+", "", account.upper())
    return bool(right) and right in left


def _is_simple_country_only_gap(party: CanonicalParty, warnings: List[Any]) -> bool:
    allowed = {
        'pass1_town_missing',
        'pass2_address_missing',
        'town_missing',
    }
    normalized = {str(w) for w in warnings}
    if not normalized:
        return False
    if any(w not in allowed and not w.startswith("country_conflict_iban_hint_only:") for w in normalized):
        return False
    return bool(party.country_town and party.country_town.country and not party.country_town.town)


def _name_just_appends_same_country(current_name: str, slm_name: str, country_code: Optional[str]) -> bool:
    if not current_name or not slm_name or not country_code:
        return False
    current = current_name.strip().upper()
    candidate = slm_name.strip().upper()
    if not candidate.startswith(current):
        return False
    suffix = candidate[len(current):].strip(" ,-/")
    if not suffix:
        return False
    return resolve_country_code(suffix) == country_code


def _restore_unit_identifier(address_line: str, raw_source: Optional[str]) -> str:
    """Restaure un identifiant d'unité (ex: APPT 4B) perdu par le SLM si le brut le contient."""
    if not address_line or not raw_source:
        return address_line

    raw_upper = str(raw_source).upper()
    addr_upper = address_line.upper()
    unit_keywords = ("APT", "APPT", "APPARTEMENT", "APP", "UNIT", "ROOM", "RM", "SUITE", "STE", "BUREAU")

    for keyword in unit_keywords:
        if keyword not in addr_upper:
            continue

        if re.search(rf"\b{re.escape(keyword)}\s+[A-Z0-9-]+\b", addr_upper):
            return address_line

        raw_match = re.search(rf"\b{re.escape(keyword)}\s+([A-Z0-9-]+)\b", raw_upper)
        if not raw_match:
            continue

        unit_value = raw_match.group(1).strip()
        if not unit_value:
            continue

        return re.sub(
            rf"\b{re.escape(keyword)}\b",
            f"{keyword} {unit_value}",
            address_line,
            count=1,
            flags=re.IGNORECASE,
        )

    return address_line


# =============================================================================
# CACHE SLM (évite les appels répétés)
# =============================================================================

class SLMCache:
    """Cache simple pour les réponses SLM"""
    
    def __init__(self, max_size: int = 100):
        self.cache = {}
        self.max_size = max_size
        self.hits = 0
        self.misses = 0
    
    def _get_key(self, text: str) -> str:
        """Génère une clé de cache"""
        # Ajout d'une version pour forcer l'invalidation de l'ancien cache corrompu
        return hashlib.md5((text + "_v3_cache_invalidation").encode()).hexdigest()[:16]
    
    def get(self, text: str) -> Optional[Dict[str, Any]]:
        """Récupère du cache"""
        key = self._get_key(text)
        if key in self.cache:
            self.hits += 1
            logger.debug(f"[SLM Cache] Hit! ({self.hits} hits, {self.misses} misses)")
            return self.cache[key]
        self.misses += 1
        return None
    
    def set(self, text: str, result: Dict[str, Any]):
        """Stocke dans le cache"""
        key = self._get_key(text)
        # LRU simple: supprime l'entrée la plus ancienne si plein
        if len(self.cache) >= self.max_size:
            oldest_key = next(iter(self.cache))
            del self.cache[oldest_key]
        self.cache[key] = result
    
    def get_stats(self) -> Dict[str, int]:
        """Statistiques du cache"""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0
        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate_percent': round(hit_rate, 1),
            'size': len(self.cache)
        }


# Instance globale du cache
_slm_cache = SLMCache(max_size=50)


# =============================================================================
# CLASSE PRINCIPALE: SLM Fallback
# =============================================================================

class E3SLMFallback:
    """Fallback SLM optimisé pour corriger les cas ambigus"""
    
    def __init__(self, ollama_url: str = OLLAMA_BASE_URL, 
                 model: str = "qwen2.5:0.5b"):
        self.ollama_url = ollama_url
        self.model = model
        self.timeout = OLLAMA_TIMEOUT_SECONDS
        self.max_retries = OLLAMA_MAX_RETRIES
        
    # =====================================================================
    # Point d'entrée principal
    # =====================================================================
    
    def apply_fallback(self, party: CanonicalParty) -> CanonicalParty:
        """
        Applique le fallback SLM si nécessaire.
        Retourne le party enrichi ou inchangé si SLM échoue.
        """
        # Vérifier si fallback nécessaire
        if not self._needs_fallback(party):
            logger.info("[E3] Fallback non nécessaire")
            return party
        
        # Vérifier le cache
        cache_key = party.raw or str(party.message_id)
        
        
            
        cached = _slm_cache.get(cache_key)
        if cached:
            logger.info("[E3] Utilisation du cache SLM")
            return self._apply_cached_result(party, cached)
        
        # Appeler le SLM
        logger.info("[E3] Appel SLM en cours...")
        slm_result = self._call_slm_optimized(party)
        
        if slm_result:
            # Mettre en cache
            _slm_cache.set(cache_key, slm_result)
            # Appliquer le résultat
            enriched = self._apply_slm_result(party, slm_result)
            logger.info("[E3] SLM appliqué avec succès")
            return enriched
        else:
            logger.warning("[E3] SLM a échoué, conservation du résultat original")
            warnings = list(_meta_get(party.meta, 'warnings', []))
            warnings.append('slm_failed')
            _meta_set(party.meta, 'warnings', warnings)
            return party
    
    # =====================================================================
    # Détection intelligente du besoin de fallback
    # =====================================================================
    
    def _needs_fallback(self, party: CanonicalParty) -> bool:
        """
        Détermine si le fallback SLM est nécessaire.
        """
        confidence = _meta_get(party.meta, 'parse_confidence', 0)
        warnings = _meta_get(party.meta, 'warnings', [])
        
        # Pas besoin si déjà très bonne confiance et aucun signal fort
        if confidence >= 0.85:
            return False

        if _is_simple_country_only_gap(party, warnings):
            return False
        
        # Liste des warnings qui justifient un fallback
        fallback_triggers = [
            'country_missing',
            'country_not_found',
            'town_missing',
            'town_not_found',
            'ambiguous_city_country',
            'ambiguous_city_country_tail',
            'name_address_mixed',
            'pass1_country_missing',
            'pass1_missing_country_town',
            'pass1_town_not_found',
            'pass2_geo_incoherent',
            'no_content_after_account',
            'name_missing',
            'requires_manual_verification',
            'pass1_town_not_official'
        ]
        
        needs_slm = any(
            any(trigger in str(w) for trigger in fallback_triggers)
            for w in warnings
        )
        
        logger.debug(f"[E3] Fallback needed: {needs_slm} (confidence={confidence}, warnings={warnings})")
        return needs_slm
    
    # =====================================================================
    # Appel SLM optimisé
    # =====================================================================
    
    def _call_slm_optimized(self, party: CanonicalParty) -> Optional[Dict[str, Any]]:
        """
        Appelle Ollama avec timeout court, retries, backoff et circuit breaker.
        """
        # Vérifier le circuit breaker
        if not _ollama_circuit_breaker.can_attempt():
            logger.warning("[E3] Circuit breaker OUVERT - SLM désactivé temporairement")
            return None
        
        prompt = self._build_structured_prompt(party)
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.05,  # Très déterministe
                "num_predict": 120,   # Réduit pour plus de rapidité
                "stop": ["\n\n", "###", "---", "Input:", "Exemple:"],
                "top_k": 5,
                "top_p": 0.3,
                "repeat_penalty": 1.1,
            }
        }
        
        for attempt in range(self.max_retries):
            try:
                start_time = time.time()
                response = requests.post(
                    f"{self.ollama_url}/api/generate",
                    json=payload,
                    timeout=(3, self.timeout)
                )
                elapsed = time.time() - start_time
                
                if response.status_code == 200:
                    result_text = response.json().get("response", "").strip()
                    logger.info(f"[E3] SLM réponse en {elapsed:.1f}s")
                    _ollama_circuit_breaker.record_success()  # Réinitialiser le circuit breaker
                    return self._parse_slm_response(result_text)
                else:
                    logger.warning(f"[E3] HTTP {response.status_code} (tentative {attempt + 1}/{self.max_retries})")
                    _ollama_circuit_breaker.record_failure()
                    
                    # Réduire le prompt pour la retry en cas d'erreur
                    if attempt < self.max_retries - 1:
                        payload["options"]["num_predict"] = max(60, payload["options"]["num_predict"] - 30)
                        wait_time = min(5, (attempt + 1) * 2)  # Backoff exponentiel: 2s, 4s, 6s...
                        logger.debug(f"[E3] Attente {wait_time}s avant retry...")
                        time.sleep(wait_time)
                    
            except requests.Timeout:
                logger.warning(
                    f"[E3] Timeout Ollama (tentative {attempt + 1}/{self.max_retries}, "
                    f"model={self.model}, timeout={self.timeout}s)"
                )
                _ollama_circuit_breaker.record_failure()
                
                if attempt < self.max_retries - 1:
                    payload["options"]["num_predict"] = max(60, payload["options"]["num_predict"] - 30)
                    wait_time = min(5, (attempt + 1) * 2)
                    logger.debug(f"[E3] Attente {wait_time}s avant retry...")
                    time.sleep(wait_time)
                    
            except requests.ConnectionError as e:
                logger.error(f"[E3] Connection error: {e}")
                _ollama_circuit_breaker.record_failure()
                break
                
            except Exception as e:
                logger.error(f"[E3] Erreur inattendue: {type(e).__name__}: {e}")
                _ollama_circuit_breaker.record_failure()
                break
        
        logger.warning("[E3] SLM n'a pas pu générer de réponse après tous les retries")
        return None
    
    
    
    
    # =====================================================================
    # Prompt structuré (format clé:valeur, plus rapide que JSON)
    # =====================================================================
    
    def _build_structured_prompt(self, party: CanonicalParty) -> str:
        """
        Construit un prompt optimisé pour des réponses rapides et précises.
        VERSION 2: EXEMPLES D'ABORD pour éviter confusion SLM petit modèle.
        """
        raw = party.raw or ""
        field_type = party.field_type
        
        # Format strict: EXEMPLES D'ABORD, puis vraies données à la fin
        prompt = f"""TÂCHE: Extraire les informations d'un message SWIFT {field_type}.

RÈGLES STRICTES:
1. name = UNIQUEMENT nom de la personne ou entreprise/société.
2. address = rue/numéro/PO BOX/Z.I./bâtiment/APPARTEMENT. NE JAMAIS inclure la ville, le pays ou le code postal dans address.
3. town = ville SEULE (PAS adresse, PAS pays, PAS postal).
4. country = code ISO 2 lettres obligatoirement (ex: TN, FR).
5. postal = code postal ou - si absent.

FORMAT RÉPONSE (5 lignes):
name: <valeur>
address: <valeur ou ->
town: <valeur>
country: <XX>
postal: <valeur ou ->

EXEMPLES:

Input: "JANE DOE\nRUE DE LA PAIX\nPARIS FRANCE"
Output:
name: JANE DOE
address: RUE DE LA PAIX
town: PARIS
country: FR
postal: -

Input: "/TN4839\n2037 ARIANA\nZ.I. CHOTRANA 2\nSOCIETE MEUBLATEX SA\nATTN DIR FINANCIER"
Output:
name: SOCIETE MEUBLATEX SA ATTN DIR FINANCIER
address: Z.I. CHOTRANA 2
town: ARIANA
country: TN
postal: 2037

Input: "ELMI AHMED\n30 RUE AHMED AMINE EL OMRANE OMRANE(EL) TN/1005 OMRANE(EL)"
Output:
name: ELMI AHMED
address: 30 RUE AHMED AMINE EL OMRANE
town: OMRANE EL
country: TN
postal: 1005

---

À TRAITER (même format, répondre UNIQUEMENT le Output):

Input: "{raw}"
Output:"""
        return prompt
    
    # =====================================================================
    # Parsing de la réponse SLM (format clé:valeur)
    # =====================================================================
    
    def _parse_slm_response(self, response: str) -> Optional[Dict[str, Any]]:
        """
        Parse la réponse structurée (format clé:valeur).
        Plus robuste que le JSON.
        """
        if not response:
            return None
        
        result = {
            'name': None,
            'address_lines': [],
            'town': None,
            'country': None,
            'postal_code': None
        }
        
        lines = response.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if ':' in line:
                key, value = line.split(':', 1)
                key = key.strip().lower()
                value = value.strip()
                
                # Ignorer les valeurs vides ou "-"
                if not value or value == '-':
                    continue
                
                if key == 'name':
                    result['name'] = value.upper()
                elif key == 'address':
                    result['address_lines'] = [value.upper()]
                elif key == 'town':
                    result['town'] = value.upper()
                elif key == 'country':
                    # Normaliser le code pays
                    country = value.upper()[:2]
                    # Force correct if the LLM is stubborn
                    if country in ['TU', 'AT', 'CH']:
                        country = 'TN'
                    if len(country) == 2 and country.isalpha():
                        result['country'] = country
                elif key == 'postal':
                    result['postal_code'] = value if value != '-' else None
        
        # Validation minimale
        if not result['name']:
            logger.warning("[E3] SLM n'a pas extrait de nom")
            return None

        result['address_lines'] = [
            line for line in result['address_lines']
            if not _looks_like_account_or_iban(line)
        ]
        if result['town'] and (
            _looks_like_account_or_iban(result['town']) or resolve_country_code(result['town'])
        ):
            result['town'] = None
        
        return result
    
    # =====================================================================
    # Application du résultat SLM
    # =====================================================================
    
    def _apply_slm_result(self, party: CanonicalParty, 
                          slm_result: Dict[str, Any]) -> CanonicalParty:
        """
        Fusionne le résultat SLM avec le party existant.
        Stratégie conservative: ne remplace que si meilleur ou manquant.
        """
        updated = False
        
        # 1. Nom (toujours prendre le SLM si différent et plus complet)
        if slm_result.get('name'):
            current_name = ' '.join(party.name) if party.name else ''
            slm_name = slm_result['name']
            current_country = party.country_town.country if party.country_town else None
            
            # Prendre prioritairement le nom du SLM si c'est un format 50K bruités
            if party.field_type == "50K":
                party.name = [slm_name]
                updated = True
                logger.debug(f"[E3] Nom forcé en 50K : {slm_name}")
            elif _name_just_appends_same_country(current_name, slm_name, current_country):
                pass
            elif current_name == "UNKNOWN" or len(slm_name) >= len(current_name) - 3 or not current_name:
                party.name = [slm_name]
                updated = True
                logger.debug(f"[E3] Nom mis à jour: {slm_name}")
        
        # 2. Adresse (ajouter si manquante)
        sanitized_addresses = [line for line in slm_result.get('address_lines', []) 
                            if not _contains_account_text(line, party.account)]
                            
        # ✅ REDONDANCE : Nettoyer la ville, le code postal et le pays des lignes d'adresse
        clean_address_lines = []
        for line in sanitized_addresses:
            c_line = line
            if slm_result.get('town') and str(slm_result['town']).upper() in c_line.upper():
                c_line = re.compile(re.escape(str(slm_result['town'])), re.IGNORECASE).sub('', c_line)
            if slm_result.get('postal') and str(slm_result['postal']) in c_line:
                c_line = c_line.replace(str(slm_result['postal']), '')
            if slm_result.get('country') and str(slm_result['country']).upper() in c_line.upper():
                c_line = re.compile(re.escape(str(slm_result['country'])), re.IGNORECASE).sub('', c_line)
            # Retirer aussi les mots comme "TUNISIE" si present
            c_line = re.compile(r'\b(?:TUNISIE|TUNISIA|TUN|TU)\b', re.IGNORECASE).sub('', c_line)
            
            c_line = c_line.strip(',.- ')
            # Retirer les espaces multiples cachés (regex)
            c_line = re.sub(r'\s{2,}', ' ', c_line).strip()
            c_line = _restore_unit_identifier(c_line, party.raw or party.account)
            
            if len(c_line) > 1:
                clean_address_lines.append(c_line)

        party.address_lines = clean_address_lines
        updated = True
        logger.debug(f"[E3] Adresse mise à jour et nettoyée: {clean_address_lines}")
        
        # 3. Pays (priorité si manquant ou différent de l'IBAN)
        if slm_result.get('country'):
            if not party.country_town or not party.country_town.country:
                party.country_town = CountryTown(
                    country=slm_result['country'],
                    town=party.country_town.town if party.country_town else None,
                    postal_code=party.country_town.postal_code if party.country_town else None
                )
                updated = True
                logger.debug(f"[E3] Pays ajouté: {slm_result['country']}")
            elif party.country_town.country != slm_result['country']:
                party.country_town.country = slm_result['country']
                updated = True
                logger.debug(f"[E3] Pays mis à jour: {slm_result['country']}")
        
        # 4. Ville (priorité si manquante ou contient adresse)
        if slm_result.get('town'):
            current_town = party.country_town.town if party.country_town else ''
            slm_town = slm_result['town']
            
            # Prendre le SLM si la ville actuelle contient des mots d'adresse ou est fausse
            address_keywords = ['PO BOX', 'RUE', 'STREET', 'AVENUE', 'DEPT', 'DEPARTMENT']
            has_address_words = bool(current_town) and any(kw in current_town for kw in address_keywords)
            
            # Priorité absolue au SLM pour corriger les villes
            if not current_town or current_town == "UNKNOWN" or has_address_words or len(slm_town) >= 3:
                if not party.country_town:
                    party.country_town = CountryTown(country=None, town=slm_town, postal_code=None)
                else:
                    party.country_town.town = slm_town
                updated = True
                logger.debug(f"[E3] Ville mise à jour par SLM: {slm_town}")
        
        # 5. Code postal
        if slm_result.get('postal_code'):
            if party.country_town:
                party.country_town.postal_code = slm_result['postal_code']
                updated = True
        
        # Mise à jour des métadonnées
        _meta_set(party.meta, 'llm_signals', ['slm_applied'])
        _meta_set(party.meta, 'fallback_used', True)

        if updated:
            # Augmenter légèrement la confiance si SLM a amélioré
            current_confidence = _meta_get(party.meta, 'parse_confidence', 0.5)
            _meta_set(party.meta, 'parse_confidence', min(0.85, current_confidence + 0.15))
            # Nettoyer les warnings résolus
            _meta_set(party.meta, 'warnings', self._clean_resolved_warnings(party))
        
        return party
    
    def _apply_cached_result(self, party: CanonicalParty, 
                             cached: Dict[str, Any]) -> CanonicalParty:
        """Applique un résultat en cache"""
        party = self._apply_slm_result(party, cached)
        _meta_set(party.meta, 'llm_signals', ['slm_applied', 'slm_cached'])
        return party
    
    def _clean_resolved_warnings(self, party: CanonicalParty) -> List[str]:
        """Supprime les warnings qui ont été résolus par le SLM"""
        warnings = _meta_get(party.meta, 'warnings', [])
        cleaned = []
        
        for w in warnings:
            w_str = str(w)
            # Supprimer les warnings résolus
            if party.country_town and party.country_town.country:
                if 'country_missing' in w_str or 'country_not_found' in w_str:
                    continue
            if party.country_town and party.country_town.town:
                if 'town_missing' in w_str or 'town_not_found' in w_str:
                    continue
            if party.name and party.name != ["UNKNOWN"]:
                if 'name_missing' in w_str:
                    continue
            cleaned.append(w)
        
        return cleaned
    
    # =====================================================================
    # Utilitaires
    # =====================================================================
    
    @staticmethod
    def get_cache_stats() -> Dict[str, int]:
        """Retourne les statistiques du cache"""
        return _slm_cache.get_stats()
    
    @staticmethod
    def clear_cache():
        """Vide le cache"""
        _slm_cache.cache.clear()
        _slm_cache.hits = 0
        _slm_cache.misses = 0
        logger.info("[E3] Cache SLM vidé")


# =============================================================================
# Fonction de compatibilité (pour l'ancien code)
# =============================================================================

def llm_fallback_50K(raw: str, field_type: str, current_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fonction legacy pour compatibilité.
    Convertit le dict en CanonicalParty, applique le fallback, retourne le dict.
    """
    from src.models import CanonicalMeta
    
    # Convertir dict en CanonicalParty
    party = CanonicalParty(
        message_id=current_result.get('message_id', 'MSG_001'),
        field_type=field_type,
        role=current_result.get('role', 'debtor'),
        raw=raw,
        account=current_result.get('account'),
        party_id=current_result.get('party_id'),
        name=current_result.get('name', ['UNKNOWN']),
        address_lines=current_result.get('address_lines', []),
        country_town=current_result.get('country_town'),
        dob=current_result.get('dob'),
        pob=current_result.get('pob'),
        org_id=current_result.get('org_id'),
        national_id=current_result.get('national_id'),
        postal_complement=current_result.get('postal_complement'),
        is_org=current_result.get('is_org', False),
        meta=CanonicalMeta(**current_result.get('meta', {
            'source_format': field_type,
            'parse_confidence': 0.5,
            'warnings': [],
            'llm_signals': [],
            'fallback_used': False
        })),
        address_validation=current_result.get('address_validation', [])
    )
    
    # Appliquer le fallback
    fallback = E3SLMFallback()
    enriched = fallback.apply_fallback(party)
    
    # Retourner comme dict (pour compatibilité)
    return enriched.to_dict() if hasattr(enriched, 'to_dict') else enriched.__dict__


def detect_ambiguity(raw: str, current_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fonction legacy pour compatibilité.
    """
    warnings = current_result.get('meta', {}).get('warnings', [])
    
    fallback_triggers = [
        'country_missing', 'town_missing', 'ambiguous_city_country',
        'name_address_mixed', 'pass1_country_missing', 'pass1_town_not_found'
    ]
    
    is_ambiguous = any(
        any(trigger in str(w) for trigger in fallback_triggers)
        for w in warnings
    )
    
    return {
        'is_ambiguous': is_ambiguous,
        'signals': warnings
    }


def needs_slm_fallback(party: CanonicalParty) -> bool:
    """Compatibility wrapper expected by pipeline.py."""
    return E3SLMFallback()._needs_fallback(party)


def apply_slm_fallback(party: CanonicalParty, model: str = "qwen2.5:0.5b") -> CanonicalParty:
    """Compatibility wrapper expected by pipeline.py."""
    return E3SLMFallback(model=model).apply_fallback(party)
