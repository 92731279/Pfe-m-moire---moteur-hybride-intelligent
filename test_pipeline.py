from src.pipeline import run_pipeline
raw = """:59:/GB29NWBK60161331926819
ACME Corporation Ltd
45 Canary Wharf
E14 5AB
United Kingdom"""
party, _ = run_pipeline(raw, "59")
print(f"Town: {party.country_town.town if party.country_town else None}")
print(f"Warnings: {party.meta.warnings}")
print(f"Rejected: {party.meta.rejected}")
print(f"SLM Fallback: {party.meta.fallback_used}")
