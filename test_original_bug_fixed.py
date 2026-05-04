#!/usr/bin/env python3
"""
Test: Reproduire le problème exact du screenshot original
Input: :50K:/123456789 + JOHN DOE CO + 10 MAIN ST + NEWYORK US
Ancien résultat: ✅ MESSAGE ACCEPTÉ avec Ville="NEVES"
Nouveau résultat: ❌ MESSAGE REJETÉ (validation échouée)
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.pipeline import run_pipeline

print("=" * 100)
print("TEST: REPRODUCTION DU BUG ORIGINAL")
print("=" * 100)

# Exact input from screenshot
test_input = """:50K:/123456789
JOHN DOE CO
10 MAIN ST
NEWYORK US"""

print(f"\nInput (exact from screenshot):")
print(test_input)
print("\n" + "-" * 100)

party, _ = run_pipeline(
    raw_message=test_input,
    message_id="ORIGINAL_BUG",
    disable_slm=False,
)

rejected = getattr(party.meta, 'rejected', False)
rejection_reasons = getattr(party.meta, 'rejection_reasons', [])
town = party.country_town.town if party.country_town else None
country = party.country_town.country if party.country_town else None
postal = party.country_town.postal_code if party.country_town else None
confidence = float(getattr(party.meta, 'parse_confidence', 0.0) or 0.0)
warnings = list(getattr(party.meta, 'warnings', []) or [])

print(f"\nRÉSULTAT:")
print(f"  Ville: {town}")
print(f"  Pays: {country}")
print(f"  Code Postal: {postal}")
print(f"  Confiance: {confidence:.2f}")
print(f"  REJETÉ: {rejected}")
print(f"\n  Raisons du rejet: {rejection_reasons}")
print(f"\n  Warnings clés:")
for w in warnings:
    w_str = str(w)
    if any(x in w_str.lower() for x in ['postal', 'inference', 'slm', 'validation', 'rejected', 'newyork']):
        print(f"    - {w_str}")

print("\n" + "=" * 100)

if rejected:
    print("✅ CORRECTION VALIDÉE!")
    print("   L'ancien bug où 'NEVES' était accepté est maintenant REJETÉ.")
    print("   Raison: Inférence postale 'NEVES' échoue la validation GeoNames.")
else:
    print("❌ PROBLÈME PERSISTANT!")
    print("   Le moteur accepte toujours des résultats non validés.")
    print("   Ville acceptée: " + str(town))

print("=" * 100)
