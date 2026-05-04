#!/usr/bin/env python3
"""Debug the GEO extraction"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.e1_parser import _extract_geo_from_free_lines, _norm

# Test what _extract_geo_from_free_lines returns for "NEW YORK US"
lines = ["JOHN DOE CO", "10 MAIN ST", "NEW YORK US"]
warnings = []

geo, consumed = _extract_geo_from_free_lines(lines, warnings)

print(f"Input lines: {lines}")
print(f"\n_extract_geo_from_free_lines returned:")
print(f"  Country: {geo.country}")
print(f"  Town: {geo.town}")
print(f"  Postal Code: {geo.postal_code}")
print(f"  Lines consumed: {consumed}")
print(f"  Warnings: {warnings}")
