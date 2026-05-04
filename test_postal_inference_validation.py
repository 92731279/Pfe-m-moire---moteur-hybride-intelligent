#!/usr/bin/env python3
"""
Test: Validation stricte POST-Inférence Postale
Vérifie que les inférences postales fausses sont REJETÉES
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pipeline import run_pipeline

# Cas problématique: "10 MAIN" est un code postal INVALIDE pour ST (São Tomé)
# Un SLM peut inférer "NEVES" (la capitale) même si le code postal est clairement faux
# On doit REJETER cette inférence car elle n'a pas de base solide
test_cases = [
    {
        "name": "Invalid postal code for ST - inférence doit être rejetée",
        "input": ":50K:/123456789\nJOHN DOE CO\n10 MAIN ST\n",  # ST sans ville explicite
        "expected_rejection": True,  # ✅ DOIT être rejeté (pas de ville + postal invalide)
    },
    {
        "name": "Valid city but bogus postal - cité devrait survivre",
        "input": ":50K:/123456789\nJOHN DOE CO\nNEW YORK US\n10MAIN",  # NEW YORK explicite
        "expected_rejection": False,  # ✅ Accepté (ville est explicite et valide)
        "expected_city": "NEW YORK"
    },
    {
        "name": "Unknown postal should NOT infer garbage",
        "input": ":50K:/123456789\nJOHN DOE CO\nXXXXXX YYYY\n",  # Pas de parseable
        "expected_rejection": True,  # ✅ DOIT être rejeté (rien ne peut être validé)
    }
]

print("=" * 100)
print("TEST: VALIDATION STRICTE POST-INFÉRENCE POSTALE")
print("=" * 100)

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
    postal = party.country_town.postal_code if party.country_town else None
    confidence = float(getattr(party.meta, 'parse_confidence', 0.0) or 0.0)
    warnings = list(getattr(party.meta, 'warnings', []) or [])
    
    print(f"Résultat:")
    print(f"  City: {town}")
    print(f"  Country: {country}")
    print(f"  Postal: {postal}")
    print(f"  Confidence: {confidence:.2f}")
    print(f"  Rejected: {rejected}")
    print(f"  Rejection reasons: {rejection_reasons}")
    print(f"  Key warnings:")
    for w in warnings:
        w_str = str(w)
        if any(x in w_str for x in ['postal_inference', 'slm', 'validation_failed', 'rejected']):
            print(f"    - {w_str[:100]}")
    
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
            print(f"  ⚠️  City: Expected '{test_case['expected_city']}', got '{town}'")

print("\n" + "=" * 100)
print("FIN DES TESTS")
print("=" * 100)
