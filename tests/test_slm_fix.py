#!/usr/bin/env python3
"""Test rapide du fix SLM E3 - vérifie que le nouveau prompt fonctionne"""

import sys
from pathlib import Path
from src.e3_slm_fallback import E3SLMFallback
from src.models import CanonicalParty, CountryTown, CanonicalMeta

# Test case: Ste Automatisme Industriel - Tunis
test_raw = """/TN5903603077019102980938
STE AUTOMATISME INDUSTRIEL
CITE ERRIADH
TUNISIE"""

# Créer un party test
meta = CanonicalMeta(
    source_format="59",
    parse_confidence=0.4,
    warnings=[
        'pass1_suburb_context_detected',
        'pass2_invalid_address_line:CITE ERRIADH'
    ]
)

party = CanonicalParty(
    message_id="TEST_MSG_001",
    field_type="59",
    role="creditor",
    raw=test_raw,
    account="/TN5903603077019102980938",
    name=["CITE ERRIADH"],  # Nom actuel incorrect
    address_lines=[],
    country_town=CountryTown(country="TR", town=None),  # Pays incorrect
    meta=meta
)

print("=" * 70)
print("TEST: SLM Prompt Fix")
print("=" * 70)
print("\n📥 INPUT:")
print(f"Raw: {repr(test_raw[:50])}...")
print(f"Current name: {party.name}")
print(f"Current country: {party.country_town.country if party.country_town else None}")

print("\n🤖 TESTING NEW PROMPT...")

# Test du SLM
slm = E3SLMFallback(model="qwen2.5:0.5b")

# Afficher le prompt généré
prompt = slm._build_structured_prompt(party)
print("\n📋 PROMPT (premiers 500 chars):")
print(prompt[:500])
print("...")

# Appeler le SLM
result = slm._call_slm_optimized(party)

if result:
    print("\n✅ SLM RESPONSE:")
    print(f"  name: {result.get('name')}")
    print(f"  address: {result.get('address_lines')}")
    print(f"  town: {result.get('town')}")
    print(f"  country: {result.get('country')}")
    print(f"  postal: {result.get('postal_code')}")
    
    # Vérifier si correct
    print("\n🔍 VALIDATION:")
    if result.get('name') == 'STE AUTOMATISME INDUSTRIEL':
        print("  ✅ Nom CORRECT")
    else:
        print(f"  ❌ Nom INCORRECT: {result.get('name')}")
    
    if result.get('country') == 'TN':
        print("  ✅ Pays CORRECT (TN = Tunisie)")
    else:
        print(f"  ❌ Pays INCORRECT: {result.get('country')}")
    
    if result.get('town') == 'TUNISIE' or result.get('town') is None:
        print("  ✅ Ville OK")
    else:
        print(f"  ⚠️  Ville: {result.get('town')}")
else:
    print("\n❌ SLM a échoué à retourner un résultat")
    sys.exit(1)

print("\n" + "=" * 70)
