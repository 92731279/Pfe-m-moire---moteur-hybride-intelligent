"""geonames_db.py — Accès à la base GeoNames SQLite"""

import sqlite3
import json
import re
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "geonames" / "db" / "geonames.sqlite"
POSTAL_MAPPINGS_PATH = BASE_DIR / "data" / "postal_mappings.json"

# feature_class acceptés pour les villes/zones habitées
VALID_FEATURE_CLASSES = ("'P'", "'A'")
VALID_FC_SQL = "feature_class IN ('P', 'A')"

# Cache des mappings postaux chargés au démarrage
_POSTAL_MAPPINGS = None

def _load_postal_mappings():
    """Charge les mappings code postal -> ville depuis le fichier JSON"""
    global _POSTAL_MAPPINGS
    if _POSTAL_MAPPINGS is not None:
        return _POSTAL_MAPPINGS
    
    _POSTAL_MAPPINGS = {}
    if not POSTAL_MAPPINGS_PATH.exists():
        return _POSTAL_MAPPINGS
    
    try:
        with open(POSTAL_MAPPINGS_PATH, 'r', encoding='utf-8') as f:
            _POSTAL_MAPPINGS = json.load(f)
    except Exception as e:
        print(f"⚠️  Erreur chargement postal_mappings.json: {e}")
    
    return _POSTAL_MAPPINGS


def _connect():
    return sqlite3.connect(str(DB_PATH))


def find_place(country_code: str, town_name: str) -> Optional[dict]:
    """
    Recherche exacte par nom ou asciiname.
    Accepte feature_class P (ville) et A (division administrative).
    Priorité aux lieux peuplés (P) puis administratifs (A).
    """
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT geonameid, name, asciiname, country_code,
                   feature_class, feature_code, population, admin1_code
            FROM geonames_places
            WHERE country_code = ?
              AND {VALID_FC_SQL}
              AND (UPPER(name) = UPPER(?)
                OR UPPER(asciiname) = UPPER(?))
            ORDER BY
                CASE feature_class
                    WHEN 'P' THEN 1
                    WHEN 'A' THEN 2
                    ELSE 3
                END,
                population DESC
            LIMIT 1
        """, (country_code, town_name, town_name))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "geonameid": row[0], "name": row[1],
            "asciiname": row[2], "country_code": row[3],
            "feature_class": row[4], "feature_code": row[5],
            "population": row[6], "admin1_code": row[7],
        }
    finally:
        conn.close()


def find_alternate_place(country_code: str, town_name: str) -> Optional[dict]:
    """
    Recherche via noms alternatifs.
    Accepte feature_class P et A.
    """
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT p.geonameid, p.name, p.asciiname, p.country_code,
                   p.feature_class, p.feature_code, p.population,
                   a.alternate_name, p.admin1_code
            FROM geonames_alternate_names a
            JOIN geonames_places p ON p.geonameid = a.geonameid
            WHERE p.country_code = ?
              AND {VALID_FC_SQL}
              AND UPPER(a.alternate_name) = UPPER(?)
            ORDER BY
                CASE p.feature_class
                    WHEN 'P' THEN 1
                    WHEN 'A' THEN 2
                    ELSE 3
                END,
                p.population DESC
            LIMIT 1
        """, (country_code, town_name))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "geonameid": row[0], "name": row[1],
            "asciiname": row[2], "country_code": row[3],
            "feature_class": row[4], "feature_code": row[5],
            "population": row[6], "matched_alternate_name": row[7],
            "admin1_code": row[8],
        }
    finally:
        conn.close()


def find_place_fuzzy(country_code: str, town_name: str) -> Optional[dict]:
    """Recherche approximative LIKE — dernier recours"""
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT geonameid, name, asciiname, country_code,
                   feature_class, feature_code, population, admin1_code
            FROM geonames_places
            WHERE country_code = ?
              AND {VALID_FC_SQL}
              AND (UPPER(name) LIKE UPPER(?)
                OR UPPER(asciiname) LIKE UPPER(?))
            ORDER BY
                CASE feature_class
                    WHEN 'P' THEN 1
                    WHEN 'A' THEN 2
                    ELSE 3
                END,
                population DESC
            LIMIT 1
        """, (country_code, f"%{town_name}%", f"%{town_name}%"))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "geonameid": row[0], "name": row[1],
            "asciiname": row[2], "country_code": row[3],
            "feature_class": row[4], "feature_code": row[5],
            "population": row[6], "admin1_code": row[7],
        }
    finally:
        conn.close()


def get_administrative_parent(country_code: str, town_name: str) -> Optional[dict]:
    """
    Résout la hiérarchie administrative d'une ville.
    
    Retourne le parent administratif principal (capitale du gouvernorat/région).
    
    Exemple:
    - Input: Enfidha (TN)
    - Output: Sousse (la capitale du gouvernorat de Sousse, admin1_code=23)
    
    Logique:
    1. Cherche la ville dans GeoNames
    2. Récupère son admin1_code (région/gouvernorat)
    3. Cherche la capitale administrative de cette région (feature_code = PPLA)
    4. Retourne la capitale
    """
    # Étape 1: Cherche la ville
    place = find_place(country_code, town_name)
    if not place:
        place = find_alternate_place(country_code, town_name)
    if not place:
        return None
    
    admin1 = place.get("admin1_code")
    if not admin1:
        return None  # Pas de région parent
    
    # ⚠️ SEULEMENT pour certains pays où cette logique de promotion est pertinente (ex: Tunisie)
    # Pour l'Europe / Amériques, les communes (PPL) sont des adresses valides et ne
    # doivent pas sauter magiquement à la capitale régionale (ex: Bastogne -> Namur = FAUX)
    COUNTRIES_REQUIRING_PROMOTION = {"TN", "DZ", "MA"} # Maghreb par défaut pour cet usage de gouvernorat
    
    if country_code.upper() not in COUNTRIES_REQUIRING_PROMOTION:
        return None
    
    # Étape 2: Cherche la capitale de cette région (PPLA = Lieu administratif de premier ordre)
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT geonameid, name, asciiname, country_code,
                   feature_class, feature_code, population, admin1_code
            FROM geonames_places
            WHERE country_code = ?
              AND admin1_code = ?
              AND feature_code IN ('PPLA', 'PPLA2')
            ORDER BY population DESC
            LIMIT 1
        """, (country_code, admin1))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "geonameid": row[0], "name": row[1],
            "asciiname": row[2], "country_code": row[3],
            "feature_class": row[4], "feature_code": row[5],
            "population": row[6], "admin1_code": row[7],
            "is_parent": True,
        }
    finally:
        conn.close()


def resolve_locality_hierarchy(country_code: str, locality_name: str) -> Optional[str]:
    """
    Résout une localité vers la ville principale (capitale du gouvernorat).
    
    Retourne le nom normalisé de la ville principale.
    
    Exemple:
    - resolve_locality_hierarchy("TN", "ENFIDHA") → "SOUSSE"
    - resolve_locality_hierarchy("TN", "SOUSSE") → "SOUSSE"  (déjà capitale)
    """
    # Cherche la localité
    place = find_place(country_code, locality_name)
    if not place:
        place = find_alternate_place(country_code, locality_name)
    
    if not place:
        return None
    
    # Si c'est déjà une capitale administrative, retourne-la
    if place.get("feature_code") in ("PPLA", "PPLA2", "PPLC"):
        return place.get("name")
    
    # Cherche le parent administratif
    parent = get_administrative_parent(country_code, locality_name)
    if parent:
        return parent.get("name")
    
    # Fallback: retourne la localité elle-même
    return place.get("name")
def get_parent_city_for_district(country_code: str, locality_name: str) -> Optional[dict]:
    """
    Identifie si une localité est un quartier (PPLX) et remonte à sa ville mère (PPL/PPLC).
    Exemple: Canary Wharf (PPLX, admin1=ENG, admin2=GLA) -> London (PPLC, ENG, GLA)
    """
    place = find_place(country_code, locality_name)
    if not place:
        place = find_alternate_place(country_code, locality_name)
    
    if not place:
        return None
        
    fc = place.get("feature_code")
    # Si c'est déjà une ville majeure ou capitale, on ne fait rien
    if fc in ('PPL', 'PPLC', 'PPLA', 'PPLA2', 'PPLA3', 'PPLA4'):
        return None
        
    # Si c'est un quartier/banlieue (PPLX) ou suburb (PPLS)
    if fc in ('PPLX', 'PPLS'):
        admin1 = place.get("admin1_code")
        
        if not admin1:
            return None
            
        # Chercher la ville PPL/PPLC/PPLA dans la même région (admin1+admin2)
        conn = _connect()
        try:
            # On a besoin de admin2_code de la place actuelle
            cur = conn.cursor()
            cur.execute("""
                SELECT admin2_code FROM geonames_places WHERE geonameid = ?
            """, (place["geonameid"],))
            row_admin2 = cur.fetchone()
            admin2 = row_admin2[0] if row_admin2 else ""
            
            # Recherche du parent (idéalement PPLC, PPLA, PPL)
            query = """
                SELECT geonameid, name, asciiname, country_code,
                       feature_class, feature_code, population, admin1_code, admin2_code
                FROM geonames_places
                WHERE country_code = ?
                  AND admin1_code = ?
                  AND feature_code IN ('PPLC', 'PPLA', 'PPLA2', 'PPL')
            """
            params = [country_code, admin1]
            
            if admin2:
                query += " AND admin2_code = ?"
                params.append(admin2)
                
            query += " ORDER BY population DESC LIMIT 1"
            
            cur.execute(query, tuple(params))
            row = cur.fetchone()
            if row:
                return {
                    "geonameid": row[0], "name": row[1],
                    "asciiname": row[2], "country_code": row[3],
                    "feature_class": row[4], "feature_code": row[5],
                    "population": row[6], "admin1_code": row[7],
                    "admin2_code": row[8],
                }
            return None
        finally:
            conn.close()
    return None


def infer_city_from_postal_code(country_code: str, postal_code: str) -> Optional[str]:
    """
    Inférence générique internationale : Code Postal + Pays → Ville
    
    Essaie successivement:
    1. Recherche exacte dans les mappings postaux (data/postal_mappings.json)
    2. Recherche préfixe (utile pour UK où E14 5AB → E14 correspond à LONDON)
    3. Nettoyage et recherche sans espaces/tirets
    
    Retourne le nom de la ville canonique si trouvée, None sinon.
    
    Exemples:
    - infer_city_from_postal_code("TN", "1000") → "TUNIS"
    - infer_city_from_postal_code("FR", "75001") → "PARIS"
    - infer_city_from_postal_code("GB", "E14 5AB") → "LONDON"
    - infer_city_from_postal_code("DE", "10115") → "BERLIN"
    """
    if not country_code or not postal_code:
        return None
    
    country_code = country_code.upper().strip()
    postal_code = postal_code.strip()
    
    mappings = _load_postal_mappings()
    if country_code not in mappings:
        return None
    
    country_data = mappings[country_code]
    
    # 1. Recherche exacte
    if postal_code in country_data:
        return country_data[postal_code]
    
    # 2. Recherche préfixe (pour systèmes postaux qui n'ont pas exactement le même format)
    # Exemple: UK "E14 5AB" → chercher "E14"
    postal_normalized = re.sub(r"[\s\-]", "", postal_code)
    if postal_normalized in country_data:
        return country_data[postal_normalized]
    
    # 3. Chercher par préfixe (les N premiers caractères)
    # Utile pour pays où les N premiers chiffres définissent la région/ville
    for prefix_len in [5, 4, 3, 2]:
        if len(postal_code) >= prefix_len:
            prefix = postal_normalized[:prefix_len]
            if prefix in country_data:
                return country_data[prefix]
    
    return None


def resolve_postal_or_town(country_code: str, postal_code: Optional[str], town_name: Optional[str]) -> Optional[str]:
    """
    Résout une localité robustement en faveur de la preuve explicite (town) avec fallback postal.
    
    Priorités:
    1. Si town est présent et valide en GeoNames → retourne town validée
    2. Si town manque mais postal présent → inférer town depuis postal
    3. Sinon → retour None
    
    Retourne (town_validé, matched_via):
    - "geonames_explicit" si town trouvée en GeoNames
    - "postal_inference" si inférée depuis code postal
    - None si impossible
    """
    # Cas 1: town explicite
    if town_name:
        result = find_place(country_code, town_name)
        if result:
            return result["name"], "geonames_explicit"
        
        result = find_alternate_place(country_code, town_name)
        if result:
            return result["name"], "geonames_explicit"
    
    # Cas 2: town manque, essayer inférence depuis postal
    if postal_code and not town_name:
        inferred_town = infer_city_from_postal_code(country_code, postal_code)
        if inferred_town:
            return inferred_town, "postal_inference"
    
    return None, None


def find_major_cities_by_country(country_code: str, limit: int = 10) -> list:
    """
    Retourne les villes principales d'un pays, triées par population.
    
    Utilisé par le fallback SLM pour avoir des candidats possibles
    quand le dictionnaire postal_mappings.json n'a pas la réponse.
    
    Exemple:
    - find_major_cities_by_country("TN") → [
        {"name": "TUNIS", "population": 728453},
        {"name": "SFAX", "population": 367948},
        ...
      ]
    """
    if not country_code:
        return []
    
    country_code = country_code.upper().strip()
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(f"""
            SELECT name, population, feature_class, feature_code, admin1_code
            FROM geonames_places
            WHERE country_code = ?
              AND feature_class = 'P'
            ORDER BY population DESC
            LIMIT ?
        """, (country_code, limit))
        
        results = []
        for row in cur.fetchall():
            results.append({
                "name": row[0],
                "population": row[1],
                "feature_class": row[2],
                "feature_code": row[3],
                "admin1_code": row[4],
            })
        return results
    finally:
        conn.close()


def infer_city_with_slm_candidate_info(country_code: str, postal_code: str) -> dict:
    """
    Prépare les données pour un fallback SLM.
    
    Retourne un dict avec:
    - postal_code: le code postal
    - country_code: le code pays
    - major_cities: les villes principales du pays (pour contexte LLM)
    - context: information contextuelle pour le prompt SLM
    
    Utilisé quand infer_city_from_postal_code() retourne None.
    
    Exemple:
    {
        "postal_code": "8000",
        "country_code": "TN",
        "major_cities": [{"name": "TUNIS", "population": ...}, ...],
        "context": "Postal code 8000 in Tunisia. Candidates: NABEUL, SFAX, ..."
    }
    """
    if not country_code or not postal_code:
        return {}
    
    country_code = country_code.upper().strip()
    major_cities = find_major_cities_by_country(country_code, limit=15)
    
    city_names = [city["name"] for city in major_cities]
    context = f"Postal code {postal_code} in {country_code}. Candidate cities: {', '.join(city_names[:5])}"
    
    return {
        "postal_code": postal_code,
        "country_code": country_code,
        "major_cities": major_cities,
        "context": context,
    }

