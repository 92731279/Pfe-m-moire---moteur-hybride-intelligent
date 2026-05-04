#!/usr/bin/env python3
"""
Debug: Pourquoi NEW YORK US n'est pas parsé?
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.e0_preprocess import preprocess
from src.e1_parser import parse_field

# Cas: NEW YORK US avec compte mal formé
test_input = """:50K:/123456789
JOHN DOE CO
NEW YORK US
10MAIN"""

print("=" * 80)
print("DEBUG: Parsing NEW YORK US")
print("=" * 80)

# E0
e0 = preprocess(test_input)
print(f"\nE0 Output:")
print(f"  Field type: {e0.meta.detected_field_type}")
print(f"  Lines: {e0.lines}")
print(f"  Detected account: {e0.meta.iban_country or 'None'}")

# E1
e1 = parse_field(e0)
print(f"\nE1 Output:")
print(f"  Name: {e1.name}")
print(f"  Address lines: {e1.address_lines}")
print(f"  Country: {e1.country_town.country if e1.country_town else None}")
print(f"  Town: {e1.country_town.town if e1.country_town else None}")
print(f"  Postal: {e1.country_town.postal_code if e1.country_town else None}")
print(f"  Confidence: {e1.meta.parse_confidence}")
print(f"  Warnings: {e1.meta.warnings[:5]}")
