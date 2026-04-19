#!/usr/bin/env python3
"""Test: Extraction de ville de zone industrielle"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from src.e1_parser import parse_field
from src.models import PreprocessResult, CanonicalMeta

# Test case: "ZONE INDUSTRIELLE ENFIDHA" + "TUNISIE"
test_raw = """/TN5905500000002978275046
SOCIETE TUNISIE OUATE
ZONE INDUSTRIELLE ENFIDHA
TUNISIE"""

# Simuler la prétraitement
pre = PreprocessResult(
    raw=test_raw,
    lines=[
        "/TN5905500000002978275046",
        "SOCIETE TUNISIE OUATE",
        "ZONE INDUSTRIELLE ENFIDHA",
        "TUNISIE"
    ],
    detected_field_type="59",
    meta=CanonicalMeta(
        detected_field_type="59",
        iban_country="TN"
    )
)

print("=" * 70)
print("TEST: Extraction ville de zone industrielle")
print("=" * 70)
print("\n📥 INPUT:")
print(test_raw)

print("\n🔍 Parsing SWIFT...")
result = parse_field(pre)

print("\n📤 OUTPUT:")
print(f"  Name: {result.name}")
print(f"  Address: {result.address_lines}")
print(f"  Country: {result.country_town.country if result.country_town else None}")
print(f"  Town: {result.country_town.town if result.country_town else None}")
print(f"  Confidence: {result.meta.parse_confidence}")
print(f"  Warnings: {result.meta.warnings}")

print("\n✅ VALIDATION:")
if result.country_town.town == "ENFIDHA":
    print("  ✅ TOWN CORRECTLY EXTRACTED: ENFIDHA")
else:
    print(f"  ❌ TOWN INCORRECT: {result.country_town.town}")

if "zone_industrielle_extracted_town" in str(result.meta.warnings):
    print("  ✅ Warning signal detected")
else:
    print("  ⚠️ No zone_industrielle signal")

print("\n" + "=" * 70)
