"""geonames_loader.py — Chargement de la base GeoNames dans SQLite"""

import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
RAW_DIR = BASE_DIR / "data" / "geonames" / "raw"
DB_DIR = BASE_DIR / "data" / "geonames" / "db"
DB_PATH = DB_DIR / "geonames.sqlite"


def create_connection():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_PATH)


def create_tables(conn: sqlite3.Connection) -> None:
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS geonames_places (
        geonameid INTEGER PRIMARY KEY,
        name TEXT, asciiname TEXT, alternatenames TEXT,
        latitude REAL, longitude REAL, feature_class TEXT, feature_code TEXT,
        country_code TEXT, admin1_code TEXT, admin2_code TEXT, admin3_code TEXT,
        admin4_code TEXT, population INTEGER, elevation INTEGER, dem INTEGER,
        timezone TEXT, modification_date TEXT
    )""")
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS geonames_alternate_names (
        alternate_name_id INTEGER PRIMARY KEY,
        geonameid INTEGER, isolanguage TEXT, alternate_name TEXT,
        is_preferred_name INTEGER, is_short_name INTEGER,
        is_colloquial INTEGER, is_historic INTEGER
    )""")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_places_country ON geonames_places(country_code)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_places_name ON geonames_places(name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_places_asciiname ON geonames_places(asciiname)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alt_geonameid ON geonames_alternate_names(geonameid)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_alt_name ON geonames_alternate_names(alternate_name)")
    conn.commit()


def load_places(conn: sqlite3.Connection, limit: int = None) -> None:
    path = RAW_DIR / "allCountries.txt"
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {path}")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM geonames_places")
    with path.open("r", encoding="utf-8") as f:
        batch = []
        for i, line in enumerate(f, start=1):
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 19:
                continue
            batch.append((
                int(parts[0]) if parts[0] else None,
                parts[1], parts[2], parts[3],
                float(parts[4]) if parts[4] else None,
                float(parts[5]) if parts[5] else None,
                parts[6], parts[7], parts[8],
                parts[10], parts[11], parts[12], parts[13],
                int(parts[14]) if parts[14] else None,
                int(parts[15]) if parts[15] else None,
                int(parts[16]) if parts[16] else None,
                parts[17], parts[18],
            ))
            if len(batch) >= 5000:
                cursor.executemany("""INSERT INTO geonames_places (
                    geonameid, name, asciiname, alternatenames, latitude, longitude,
                    feature_class, feature_code, country_code, admin1_code, admin2_code,
                    admin3_code, admin4_code, population, elevation, dem, timezone, modification_date
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", batch)
                conn.commit()
                batch = []
            if limit and i >= limit:
                break
        if batch:
            cursor.executemany("""INSERT INTO geonames_places (
                geonameid, name, asciiname, alternatenames, latitude, longitude,
                feature_class, feature_code, country_code, admin1_code, admin2_code,
                admin3_code, admin4_code, population, elevation, dem, timezone, modification_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", batch)
            conn.commit()


def load_alternate_names(conn: sqlite3.Connection, limit: int = None) -> None:
    path = RAW_DIR / "alternateNamesV2.txt"
    if not path.exists():
        raise FileNotFoundError(f"Fichier introuvable: {path}")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM geonames_alternate_names")
    with path.open("r", encoding="utf-8") as f:
        batch = []
        for i, line in enumerate(f, start=1):
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 8:
                continue
            batch.append((
                int(parts[0]) if parts[0] else None,
                int(parts[1]) if parts[1] else None,
                parts[2], parts[3],
                1 if parts[4] == "1" else 0,
                1 if parts[5] == "1" else 0,
                1 if parts[6] == "1" else 0,
                1 if parts[7] == "1" else 0,
            ))
            if len(batch) >= 5000:
                cursor.executemany("""INSERT INTO geonames_alternate_names (
                    alternate_name_id, geonameid, isolanguage, alternate_name,
                    is_preferred_name, is_short_name, is_colloquial, is_historic
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", batch)
                conn.commit()
                batch = []
            if limit and i >= limit:
                break
        if batch:
            cursor.executemany("""INSERT INTO geonames_alternate_names (
                alternate_name_id, geonameid, isolanguage, alternate_name,
                is_preferred_name, is_short_name, is_colloquial, is_historic
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""", batch)
            conn.commit()


def build_database(limit_places: int = None, limit_alternate: int = None) -> None:
    conn = create_connection()
    try:
        create_tables(conn)
        load_places(conn, limit=limit_places)
        load_alternate_names(conn, limit=limit_alternate)
        print(f"Base créée avec succès : {DB_PATH}")
    finally:
        conn.close()


if __name__ == "__main__":
    build_database()
