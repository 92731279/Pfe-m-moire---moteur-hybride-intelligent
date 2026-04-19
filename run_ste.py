from src.pipeline import run_pipeline
import pprint
result, _ = run_pipeline("""\
:59:/TN5903603077019102980938
STE AUTOMATISME INDUSTRIEL
CITE ERRIADH
TUNISIE""")
print(f"Town: {result.country_town.town}")
print(f"Confidence: {result.meta.parse_confidence}")
print(f"Warnings: {result.meta.warnings}")
print(f"Rejected: {result.meta.rejected}")
print(f"SLM Fallback: {result.meta.fallback_used}")

