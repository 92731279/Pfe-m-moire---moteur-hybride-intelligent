"""geonames_db.py — Accès à la base GeoNames SQLite"""

import sqlite3
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "data" / "geonames" / "db" / "geonames.sqlite"


def _connect():
    return sqlite3.connect(DB_PATH)


def find_place(country_code: str, town_name: str) -> Optional[dict]:
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT geonameid, name, asciiname, country_code, feature_code, population
            FROM geonames_places
            WHERE country_code = ?
              AND (UPPER(name) = UPPER(?) OR UPPER(asciiname) = UPPER(?))
            ORDER BY population DESC
            LIMIT 1
        """, (country_code, town_name, town_name))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "geonameid": row[0], "name": row[1], "asciiname": row[2],
            "country_code": row[3], "feature_code": row[4], "population": row[5],
        }
    finally:
        conn.close()


def find_alternate_place(country_code: str, town_name: str) -> Optional[dict]:
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT p.geonameid, p.name, p.asciiname, p.country_code,
                   p.feature_code, p.population, a.alternate_name
            FROM geonames_alternate_names a
            JOIN geonames_places p ON p.geonameid = a.geonameid
            WHERE p.country_code = ?
              AND UPPER(a.alternate_name) = UPPER(?)
            ORDER BY p.population DESC
            LIMIT 1
        """, (country_code, town_name))
        row = cur.fetchone()
        if not row:
            return None
        return {
            "geonameid": row[0], "name": row[1], "asciiname": row[2],
            "country_code": row[3], "feature_code": row[4],
            "population": row[5], "matched_alternate_name": row[6],
        }
    finally:
        conn.close()


if __name__ == "__main__":
    print("TEST PARIS:")
    print(find_place("FR", "PARIS"))
    print("\nTEST VARIANTE (ex: OUED REMEL):")
    print(find_alternate_place("TN", "OUED REMEL"))
