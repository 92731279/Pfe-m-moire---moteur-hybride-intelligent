#!/usr/bin/env python3
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.models import CanonicalParty, CanonicalMeta, CountryTown
from src.e3_slm_fallback import needs_slm_fallback, apply_slm_fallback

def create_test_party():
    return CanonicalParty(
        message_id="TEST_001",
        field_type="MT103",
        role="debtor",
        raw="JOHN DOE, 123 RUE PARIS, PARIS",
        name=["JOHN DOE"],
        address_lines=["123 RUE PARIS"],
        country_town=CountryTown(country=None, town="PARIS", postal_code=None),
        is_org=False,
        account="FR1234567890",
        meta=CanonicalMeta(
            source_format="MT103",
            parse_confidence=0.5,
            warnings=["country_missing", "town_not_found"],
            llm_signals=[],
            fallback_used=False
        )
    )

print("="*60)
print(" Testing E3 Fixes")
print("="*60)

print("\n1️⃣  Test: Détection SLM fallback")
party = create_test_party()
if needs_slm_fallback(party):
    print("✅ SLM fallback détecté")
else:
    print("❌ SLM fallback non détecté")

print("\n2️⃣  Test: Appliquer SLM fallback")
print("  Appel SLM...")
start = time.time()
result = apply_slm_fallback(party, model="phi3:mini")
elapsed = time.time() - start
print(f"  ✅ Appel en {elapsed:.1f}s")
print(f"  Fallback utilisé: {result.meta.fallback_used}")

print("\n3️⃣  Test: Circuit Breaker")
from src.e3_slm_fallback import _ollama_circuit_breaker
print(f"  État: open={_ollama_circuit_breaker.is_open}")
_ollama_circuit_breaker.record_failure()
_ollama_circuit_breaker.record_failure()
print(f"  Après 2 failures: open={_ollama_circuit_breaker.is_open}")
if _ollama_circuit_breaker.is_open:
    print("✅ Circuit breaker fonctionne")
else:
    print("❌ Circuit breaker ne s'est pas ouvert")

print("\n" + "="*60)
print("✅ Tests terminés")
print("="*60)
