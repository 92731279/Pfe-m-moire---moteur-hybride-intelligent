#!/usr/bin/env python3
"""
Test: Validation stricte POST-SLM
Vérifie que les résultats SLM non validés par GeoNames sont REJETÉS
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pipeline import run_pipeline

# Cas 1: NEWYORK (sans espace) - SLM va retourner "NEW YORK" ou "NEWYORK"
# Mais GeoNames ne va pas le confirmer, donc devrait être REJETÉ
test_cases = [
    {
        "name": "NEWYORK US (sans espace) - SLM doit être validé",
        "input": ":50K:/123456789\nJOHN DOE CO\n10 MAIN ST\nNEWYORK US",
        "expected_rejection": True,  # ✅ DOIT être rejeté car SLM validation échoue
        "expected_city_reason": "slm_validation_failed"
    },
    {
        "name": "NEW YORK US (avec espace) - Parsing direct fonctionne",
        "input": ":50K:/123456789\nJOHN DOE CO\n10 MAIN ST\nNEW YORK US",
        "expected_rejection": False,  # ✅ Devrait être accepté (parsing direct, pas SLM)
        "expected_city": "NEW YORK"
    },
    {
        "name": "PARIS FRANCE - Parsing direct connu",
        "input": ":50K:/FR123\nJANE DOE\n5 RUE DE LA PAIX\nPARIS FRANCE",
        "expected_rejection": False,  # ✅ Devrait être accepté
        "expected_city": "PARIS"
    }
]

print("=" * 80)
print("TEST: VALIDATION STRICTE POST-SLM")
print("=" * 80)

for i, test_case in enumerate(test_cases, 1):
    print(f"\n[Test {i}] {test_case['name']}")
    print(f"Input:\n{test_case['input']}\n")
    
    party, _ = run_pipeline(
        raw_message=test_case["input"],
        message_id=f"TEST_{i}",
        slm_model="qwen2.5:0.5b",
        disable_slm=False,  # ✅ Force SLM
    )
    
    rejected = getattr(party.meta, 'rejected', False)
    rejection_reasons = getattr(party.meta, 'rejection_reasons', [])
    town = party.country_town.town if party.country_town else None
    country = party.country_town.country if party.country_town else None
    confidence = float(getattr(party.meta, 'parse_confidence', 0.0) or 0.0)
    warnings = list(getattr(party.meta, 'warnings', []) or [])
    
    print(f"Résultat:")
    print(f"  City: {town}")
    print(f"  Country: {country}")
    print(f"  Confidence: {confidence:.2f}")
    print(f"  Rejected: {rejected}")
    print(f"  Rejection reasons: {rejection_reasons}")
    print(f"  Warnings: {[str(w) for w in warnings[:5]]}")  # First 5 warnings
    
    # Vérification
    if "expected_rejection" in test_case:
        if rejected == test_case["expected_rejection"]:
            print(f"  ✅ PASS: Rejection status correct")
        else:
            print(f"  ❌ FAIL: Expected rejected={test_case['expected_rejection']}, got {rejected}")
    
    if "expected_city" in test_case:
        if town == test_case["expected_city"]:
            print(f"  ✅ PASS: City correct")
        else:
            print(f"  ❌ FAIL: Expected city={test_case['expected_city']}, got {town}")
    
    if "expected_city_reason" in test_case:
        if test_case["expected_city_reason"] in str(rejection_reasons):
            print(f"  ✅ PASS: Rejection reason correct")
        else:
            print(f"  ❌ FAIL: Expected reason containing '{test_case['expected_city_reason']}', got {rejection_reasons}")

print("\n" + "=" * 80)
print("FIN DES TESTS")
print("=" * 80)
