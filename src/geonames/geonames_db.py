"""geonames_db.py — Accès à la base GeoNames SQLite"""

import sqlite3
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "geonames" / "db" / "geonames.sqlite"

# feature_class acceptés pour les villes/zones habitées
VALID_FEATURE_CLASSES = ("'P'", "'A'")
VALID_FC_SQL = "feature_class IN ('P', 'A')"


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