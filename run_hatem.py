from src.pipeline import run_pipeline
result, _ = run_pipeline("""\
:50K:/TN5903135120016916920257
HATEM KHADIMALLAH
1050 CARIBBEAN WAY MIAMI FL 33132
USA""")
print(f"Town: {result.country_town.town}")
print(f"Postal: {result.country_town.postal_code}")
print(f"Confidence: {result.meta.parse_confidence}")
print(f"Warnings: {result.meta.warnings}")
print(f"Rejected: {result.meta.rejected}")

