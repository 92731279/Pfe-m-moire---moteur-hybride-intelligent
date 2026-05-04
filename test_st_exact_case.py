#!/usr/bin/env python3
"""
Test: Reproduire le cas EXACT du screenshot
- Pays: ST (São Tomé)
- Postal: "10 MAIN" (invalide)
- Ancien résultat: Ville inférée="NEVES", ✅ ACCEPTÉ
- Nouveau résultat: REJETÉ (validation échouée)
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pipeline import run_pipeline

print("=" * 100)
print("TEST: CAS EXACT DU SCREENSHOT (ST avec postal invalide)")
print("=" * 100)

# Force ST parsing with invalid postal
test_cases = [
    {
        "name": "ST + 10 MAIN → devrait INFÉRER ville mais validation échoue",
        "input": ":50K:/123456789\nJOHN DOE CO\n10 MAIN ST\n",  # ST at end (country code)
        "description": "Postal invalide (10 MAIN) + Pays ST → SLM/inférence essayera"
    },
    {
        "name": "Cas avec IBAN ST explicite",
        "input": ":50K:/ST123456\nJOHN DOE CO\n10 MAIN ST",
        "description": "IBAN commence par ST"
    }
]

for test_case in test_cases:
    print(f"\n[Test] {test_case['name']}")
    print(f"  {test_case['description']}")
    print(f"\nInput:\n{test_case['input']}\n")
    
    party, _ = run_pipeline(
        raw_message=test_case["input"],
        message_id="BUG_EXACT",
        disable_slm=False,
    )
    
    rejected = getattr(party.meta, 'rejected', False)
    rejection_reasons = getattr(party.meta, 'rejection_reasons', [])
    town = party.country_town.town if party.country_town else None
    country = party.country_town.country if party.country_town else None
    postal = party.country_town.postal_code if party.country_town else None
    warnings = list(getattr(party.meta, 'warnings', []) or [])
    
    print(f"  Résultat:")
    print(f"    Ville: {town}")
    print(f"    Pays: {country}")
    print(f"    Postal: {postal}")
    print(f"    REJETÉ: {rejected}")
    
    # Chercher les warnings d'inférence postale
    postal_warnings = [w for w in warnings if 'postal_inference' in str(w).lower()]
    
    if postal_warnings:
        print(f"    Postal Inference Warnings:")
        for w in postal_warnings:
            print(f"      - {w}")
    
    # Évaluation
    if country == "ST" and postal_warnings:
        if rejected:
            print(f"    ✅ CORRECT: Inférence rejetée (validation échouée)")
        else:
            print(f"    ❌ PROBLÈME: Inférence acceptée sans validation")
    
    print()
