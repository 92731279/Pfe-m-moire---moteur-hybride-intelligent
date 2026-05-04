#!/usr/bin/env python3
"""Quick test for NEW YORK parsing fix"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from src.pipeline import run_pipeline
from src.e0_preprocess import preprocess

test_input = ":50K:/123456789\nJOHN DOE CO\n10 MAIN ST\nNEW YORK US"

# Parse
pre = preprocess(test_input)
print(f"Input parsed as {len(pre.lines)} lines")

# Run pipeline
result, _ = run_pipeline(test_input, disable_slm=True)

print(f"\n✅ RESULTS:")
print(f"  Town: {result.country_town.town if result.country_town else 'N/A'}")
print(f"  Postal: {result.country_town.postal_code if result.country_town else 'N/A'}")
print(f"  Country: {result.country_town.country if result.country_town else 'N/A'}")
print(f"  Confidence: {result.meta.parse_confidence}")
print(f"  REJECTED: {result.meta.rejected}")
print(f"  Manual Review Required: {getattr(result.meta, 'requires_manual_review', False)}")

if result.meta.rejected:
    print(f"  Rejection Reasons: {result.meta.rejection_reasons}")
