#!/usr/bin/env python3
"""
Test: Fallback SLM pour inférence code postal → ville
Teste les cas où postal_mappings.json n'a pas la réponse
"""

from src.pipeline import run_pipeline
from src.geonames.geonames_db import (
    infer_city_from_postal_code,
    find_major_cities_by_country,
    infer_city_with_slm_candidate_info
)
from src.postal_slm_fallback import infer_city_via_slm_postal, needs_postal_slm_fallback


def test_dictionary_coverage():
    """Tester que le dictionnaire couvre bien les cas principaux"""
    print("\n✅ TEST 1: Couverture du dictionnaire postal_mappings.json")
    print("="*70)
    
    test_cases = [
        ("TN", "1000", "TUNIS"),
        ("FR", "75001", "PARIS"),
        ("GB", "E14", "LONDON"),
        ("US", "10001", "NEW YORK"),
    ]
    
    passed = 0
    for country, postal, expected in test_cases:
        result = infer_city_from_postal_code(country, postal)
        status = "✅" if result == expected else "❌"
        print(f"  {status} {country}/{postal} → {result} (attendu: {expected})")
        if result == expected:
            passed += 1
    
    print(f"\nScore: {passed}/{len(test_cases)} ✅\n")
    return passed == len(test_cases)


def test_slm_fallback_decision():
    """Tester que le fallback SLM est décidé correctement"""
    print("\n✅ TEST 2: Décision de fallback SLM")
    print("="*70)
    
    test_cases = [
        # (country, postal, town) -> should_use_slm
        ("TN", "9999", None, True),      # Postal inconnu du dictionnaire
        ("XY", "12345", None, True),     # Pays non supporté
        ("TN", "1000", None, False),     # Postal dans dictionnaire (sera capté avant SLM)
        ("TN", None, None, False),       # Pas de postal
        ("TN", "8000", "NABEUL", False), # Ville déjà présente
    ]
    
    passed = 0
    for country, postal, town, should_use in test_cases:
        result = needs_postal_slm_fallback(country, postal, town)
        status = "✅" if result == should_use else "❌"
        print(f"  {status} {country}/{postal}/{town} → SLM={result} (attendu: {should_use})")
        if result == should_use:
            passed += 1
    
    print(f"\nScore: {passed}/{len(test_cases)} ✅\n")
    return passed == len(test_cases)


def test_geonames_candidates():
    """Tester que GeoNames retourne les candidats correctement"""
    print("\n✅ TEST 3: Candidats GeoNames par pays")
    print("="*70)
    
    countries = ["TN", "FR", "US", "GB", "DE", "CN", "JP"]
    all_ok = True
    
    for country in countries:
        cities = find_major_cities_by_country(country, limit=5)
        if cities:
            print(f"  ✅ {country}: {len(cities)} villes trouvées")
            print(f"      Top 3: {', '.join([c['name'] for c in cities[:3]])}")
        else:
            print(f"  ❌ {country}: Pas de villes trouvées!")
            all_ok = False
    
    print()
    return all_ok


def test_slm_candidate_info():
    """Tester que les infos candidate pour SLM sont bien formées"""
    print("\n✅ TEST 4: Infos candidates pour SLM")
    print("="*70)
    
    test_cases = [
        ("TN", "9999"),  # Postal inconnu
        ("FR", "13000"), # Postal inconnu (Marseille)
        ("US", "77002"), # Postal inconnu (Houston)
    ]
    
    for country, postal in test_cases:
        info = infer_city_with_slm_candidate_info(country, postal)
        if info and info.get("major_cities"):
            print(f"  ✅ {country}/{postal}:")
            print(f"      Context: {info.get('context', 'N/A')[:70]}...")
            print(f"      Candidats: {len(info['major_cities'])} villes")
        else:
            print(f"  ❌ {country}/{postal}: Pas de candidats")
    
    print()


def test_pipeline_with_unknown_postal():
    """Tester le pipeline avec un code postal non couvert par le dictionnaire"""
    print("\n✅ TEST 5: Pipeline avec code postal non couvert")
    print("="*70)
    
    # Créer un message avec un code postal qui n'est PAS dans postal_mappings.json
    # (par exemple, un code postal réel mais non listé)
    msg = """:59:/TN5914700002202576951487
SOCIETE INCONNUE
RUE PRINCIPALE
9999
TUNISIE"""
    
    print(f"Message: Code postal TN/9999 (non couvert)")
    result, _ = run_pipeline(msg, message_id="TEST_UNKNOWN_POSTAL")
    
    ct = result.country_town
    print(f"\nRésultat:")
    print(f"  Country: {ct.country}")
    print(f"  Town:    {ct.town}")
    print(f"  Postal:  {ct.postal_code}")
    
    # Vérifier qu'une tentative d'inférence a été faite
    warnings_relevant = [w for w in result.meta.warnings if "postal_inference" in str(w).lower()]
    if warnings_relevant:
        print(f"  ✅ Inférence tentée: {warnings_relevant}")
    else:
        print(f"  ⚠️  Pas d'inférence (peut-être que le code postal est valide en GeoNames)")
    
    print()


if __name__ == "__main__":
    print("""
🧪 TESTS: FALLBACK SLM POUR INFÉRENCE POSTAL
═════════════════════════════════════════════════════════════════════
""")
    
    results = []
    
    # Test 1: Dictionary coverage
    results.append(("Dictionary Coverage", test_dictionary_coverage()))
    
    # Test 2: SLM decision logic
    results.append(("SLM Decision", test_slm_fallback_decision()))
    
    # Test 3: GeoNames candidates
    results.append(("GeoNames Candidates", test_geonames_candidates()))
    
    # Test 4: Candidate info for SLM
    test_slm_candidate_info()
    
    # Test 5: Pipeline integration
    test_pipeline_with_unknown_postal()
    
    # Summary
    print("\n" + "="*70)
    print("📊 RÉSUMÉ DES TESTS")
    print("="*70)
    for name, passed in results:
        status = "✅" if passed else "❌"
        print(f"{status} {name}")
    
    all_passed = all(p for _, p in results)
    if all_passed:
        print("\n🎉 TOUS LES TESTS RÉUSSIS!")
    else:
        print("\n⚠️  Certains tests ont échoué")
