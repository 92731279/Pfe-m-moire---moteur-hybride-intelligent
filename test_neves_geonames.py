#!/usr/bin/env python3
"""
Debug: Est-ce que NEVES existe en GeoNames pour ST?
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.geonames.geonames_db import find_place

print("Vérification si NEVES existe en GeoNames pour ST...")
result = find_place("ST", "NEVES")
print(f"Result: {result}")

if result:
    print("✅ NEVES existe en GeoNames pour ST - donc c'est techniquement valide!")
    print("Donc ma validation ne le rejette PAS.")
else:
    print("❌ NEVES n'existe pas en GeoNames pour ST")
