from src.pipeline import run_pipeline
result, _ = run_pipeline("""\
:59:/815203590096536
BEN TALEB CHOKRI
8846 RUE VALADE
QUEBEC QC G1G6L5 CA""")
print(f"Town: {result.country_town.town}")
print(f"Postal: {result.country_town.postal_code}")
print(f"Confidence: {result.meta.parse_confidence}")
print(f"Warnings: {result.meta.warnings}")
print(f"Rejected: {result.meta.rejected}")

