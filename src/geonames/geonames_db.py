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
                   feature_class, feature_code, population
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
            "population": row[6],
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
                   a.alternate_name
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
                   feature_class, feature_code, population
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
            "population": row[6],
        }
    finally:
        conn.close()