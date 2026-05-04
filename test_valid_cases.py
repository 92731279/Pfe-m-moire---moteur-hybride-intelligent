#!/usr/bin/env python3
"""
Test: Vrais cas d'usage doivent TOUJOURS marcher
Vérifier que les fixes n'ont pas cassé les cas valides
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pipeline import run_pipeline

test_cases = [
    {
        "name": "Cas normal USA - ACCEPTÉ",
        "input": ":50K:/US123456789\nJOHN DOE CORP\n123 MAIN STREET\nNEW YORK NY 10001 US",
        "should_pass": True,
    },
    {
        "name": "Cas normal FRANCE - ACCEPTÉ",
        "input": ":50K:/FR123456789\nSOCIETE MEUBLATEX SA\n5 RUE DE LA PAIX\nPARIS 75000 FR",
        "should_pass": True,
    },
    {
        "name": "Cas simple: Juste ville + pays",
        "input": ":50K:/123456\nJANE DOE\nLONDON GB",
        "should_pass": True,
    },
]

print("=" * 100)
print("TEST: VALIDATION DES CAS VALIDES (No Regression)")
print("=" * 100)

passed = 0
failed = 0

for i, test_case in enumerate(test_cases, 1):
    print(f"\n[Test {i}] {test_case['name']}")
    
    party, _ = run_pipeline(
        raw_message=test_case["input"],
        message_id=f"VALID_{i}",
        disable_slm=False,
    )
    
    rejected = getattr(party.meta, 'rejected', False)
    town = party.country_town.town if party.country_town else None
    country = party.country_town.country if party.country_town else None
    confidence = float(getattr(party.meta, 'parse_confidence', 0.0) or 0.0)
    
    is_pass = rejected == (not test_case["should_pass"])
    
    print(f"  Accepted: {not rejected} | City: {town} | Country: {country} | Conf: {confidence:.2f}")
    
    if is_pass:
        print(f"  ✅ PASS")
        passed += 1
    else:
        print(f"  ❌ FAIL")
        failed += 1
        if test_case["should_pass"] and rejected:
            print(f"     -> Was supposed to be ACCEPTED but was REJECTED")
            print(f"     -> Reasons: {getattr(party.meta, 'rejection_reasons', [])}")

print("\n" + "=" * 100)
print(f"Results: {passed} passed, {failed} failed")
print("=" * 100)
