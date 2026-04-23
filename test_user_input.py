from src.pipeline import run_pipeline
msg = """:50F:/TN5908003000515000036157
1/MR BEN GAMRA MOHAMED AMINE
2/AAABBB
3/TN/PARIS"""
res, _ = run_pipeline(msg)
print("Nom :", res.name)
print("Adresse :", res.address_lines)
print("Rejected:", res.meta.rejected)
