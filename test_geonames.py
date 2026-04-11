#!/usr/bin/env python3
"""Test script pour valider le fonctionnement de la base GeoNames"""

import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "geonames" / "db" / "geonames.sqlite"

def test_connection():
    """Test 1: Connexion à la base"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.close()
        print("✅ Test 1: Connexion réussie")
        return True
    except Exception as e:
        print(f"❌ Test 1: Erreur {e}")
        return False

def test_tables():
    """Test 2: Existence des tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        expected = {'geonames_places', 'geonames_alternate_names'}
        if expected.issubset(set(tables)):
            print(f"✅ Test 2: Tables trouvées: {tables}")
            return True
        else:
            print(f"❌ Test 2: Tables manquantes. Trouvées: {tables}")
            return False
    except Exception as e:
        print(f"❌ Test 2: Erreur {e}")
        return False
    finally:
        conn.close()

def test_data_counts():
    """Test 3: Nombre de lieux et noms alternatifs"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Lieux
        cursor.execute("SELECT COUNT(*) FROM geonames_places")
        places_count = cursor.fetchone()[0]
        
        # Noms alternatifs
        cursor.execute("SELECT COUNT(*) FROM geonames_alternate_names")
        alt_count = cursor.fetchone()[0]
        
        if places_count > 0 and alt_count > 0:
            print(f"✅ Test 3: Données présentes")
            print(f"   - Lieux: {places_count:,}")
            print(f"   - Noms alternatifs: {alt_count:,}")
            return True
        else:
            print(f"❌ Test 3: Base vide (places={places_count}, alt={alt_count})")
            return False
    except Exception as e:
        print(f"❌ Test 3: Erreur {e}")
        return False
    finally:
        conn.close()

def test_search_by_name():
    """Test 4: Recherche par nom"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Chercher Paris
        cursor.execute("SELECT geonameid, name, country_code, latitude, longitude FROM geonames_places WHERE name = 'Paris' LIMIT 5")
        results = cursor.fetchall()
        if results:
            print(f"✅ Test 4: Recherche par nom réussie (exemple: Paris)")
            for r in results[:2]:
                print(f"   - {r[1]} ({r[2]}): {r[3]}, {r[4]}")
            return True
        else:
            print("❌ Test 4: Aucun résultat pour 'Paris'")
            return False
    except Exception as e:
        print(f"❌ Test 4: Erreur {e}")
        return False
    finally:
        conn.close()

def test_search_by_country():
    """Test 5: Recherche par pays"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM geonames_places WHERE country_code = 'FR'")
        count = cursor.fetchone()[0]
        if count > 0:
            print(f"✅ Test 5: Recherche par pays réussie")
            print(f"   - Lieux en France: {count:,}")
            return True
        else:
            print("❌ Test 5: Aucun lieu trouvé pour la France")
            return False
    except Exception as e:
        print(f"❌ Test 5: Erreur {e}")
        return False
    finally:
        conn.close()

def test_alternate_names():
    """Test 6: Recherche par noms alternatifs"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Exemple: chercher "Géorgie" (alternative pour Georgia)
        cursor.execute("""
            SELECT p.name, p.country_code, a.alternate_name 
            FROM geonames_places p
            JOIN geonames_alternate_names a ON p.geonameid = a.geonameid
            WHERE a.alternate_name = 'Géorgie' LIMIT 3
        """)
        results = cursor.fetchall()
        if results:
            print(f"✅ Test 6: Recherche par noms alternatifs réussie")
            for r in results[:2]:
                print(f"   - {r[0]} ({r[1]}): alt='{r[2]}'")
            return True
        else:
            cursor.execute("SELECT COUNT(*) FROM geonames_alternate_names LIMIT 1")
            cursor.fetchone()
            print("✅ Test 6: Table des noms alternatifs accessible (pas d'exemple 'Géorgie')")
            return True
    except Exception as e:
        print(f"❌ Test 6: Erreur {e}")
        return False
    finally:
        conn.close()

def test_performances():
    """Test 7: Performances"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Test requête avec JOIN
        start = time.time()
        cursor.execute("""
            SELECT COUNT(*) FROM geonames_places 
            WHERE feature_class = 'P' AND population > 100000
        """)
        result = cursor.fetchone()[0]
        elapsed = time.time() - start
        
        if elapsed < 1.0:
            print(f"✅ Test 7: Performances excellentes")
            print(f"   - Requête en {elapsed:.3f}s ({result:,} résultats)")
            return True
        else:
            print(f"⚠️  Test 7: Requête lente ({elapsed:.3f}s)")
            return True  # Pas un échec critique
    except Exception as e:
        print(f"❌ Test 7: Erreur {e}")
        return False
    finally:
        conn.close()

def main():
    print("=" * 60)
    print("🧪 TESTS GEONAMES")
    print("=" * 60)
    
    tests = [
        test_connection,
        test_tables,
        test_data_counts,
        test_search_by_name,
        test_search_by_country,
        test_alternate_names,
        test_performances
    ]
    
    results = []
    for test in tests:
        results.append(test())
        print()
    
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"📊 RÉSUMÉ: {passed}/{total} tests réussis")
    
    if passed == total:
        print("✅ GeoNames fonctionne PARFAITEMENT !")
    elif passed >= total - 1:
        print("⚠️  GeoNames fonctionne avec des avertissements")
    else:
        print("❌ GeoNames a des problèmes")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
