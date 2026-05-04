#!/usr/bin/env python3
"""
Test: Détection correcte du type de partie (Personne vs Organisation)
Vérifier que "JOHN DOE CO" est maintenant détecté comme Personne (CO = Colorado)
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pipeline import run_pipeline

test_cases = [
    {
        "name": "JOHN DOE CO (CO = Colorado, US state code)",
        "input": ":50K:/123456789\nJOHN DOE CO\n10 MAIN ST",
        "expected_type": False,  # False = Personne
    },
    {
        "name": "JOHN DOE COMPANY (vraie organisation)",
        "input": ":50K:/123456789\nJOHN DOE COMPANY\n10 MAIN ST",
        "expected_type": True,  # True = Organisation
    },
    {
        "name": "ACME CORP (vraie organisation)",
        "input": ":50K:/123456789\nACME CORP\n123 BUSINESS AVE",
        "expected_type": True,
    },
    {
        "name": "JANE MARIE SMITH (personne)",
        "input": ":50K:/123456789\nJANE MARIE SMITH\n789 OAK STREET",
        "expected_type": False,
    },
]

print("=" * 100)
print("TEST: DÉTECTION DU TYPE DE PARTIE (Personne vs Organisation)")
print("=" * 100)

passed = 0
failed = 0

for test_case in test_cases:
    print(f"\n[Test] {test_case['name']}")
    print(f"Input: {test_case['input'].split(chr(10))[1]}")
    
    party, _ = run_pipeline(
        raw_message=test_case["input"],
        message_id="TEST_TYPE_DETECTION",
        disable_slm=True,  # Pas besoin de SLM pour ce test
    )
    
    is_org = party.is_org
    expected = test_case['expected_type']
    
    type_str = "Organisation" if is_org else "Personne"
    expected_str = "Organisation" if expected else "Personne"
    
    print(f"  Détecté: {type_str}")
    print(f"  Attendu: {expected_str}")
    
    if is_org == expected:
        print(f"  ✅ PASS")
        passed += 1
    else:
        print(f"  ❌ FAIL")
        failed += 1

print("\n" + "=" * 100)
print(f"Résultats: {passed} passed, {failed} failed")
print("=" * 100)
