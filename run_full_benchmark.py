import pandas as pd
import time
from src.pipeline import run_pipeline

def build_raw_message(group: pd.DataFrame) -> str:
    group = group.sort_values(by="ORDRE")
    champ = str(group.iloc[0]["CHAMPS"]).replace('F', '', 1)
    lines = [f":{champ}:"]
    for _, row in group.iterrows():
        sc = str(row["SOUS_CHAMPS"]).upper()
        val = str(row["VALEUR"])
        if val == "nan": continue
        if sc == "COMPTE":
            lines[0] += ("/" + val if not val.startswith("/") else val)
        else:
            lines.append(val)
    return "\n".join(lines)

print("Chargement complet du dataset MT103.xls...")
df = pd.read_excel("data/MT103.xls")
df_parties = df[df["CHAMPS"].isin(["F50K", "F50F", "F59", "F59F"])]
grouped = list(df_parties.groupby(["NUM_SWIFT", "CHAMPS"]))

results = []
total = len(grouped)
print(f"Lancement du Moteur sur la totalité du dataset : {total} messages.")

for i, ((num, champ), group) in enumerate(grouped):
    raw = build_raw_message(group)
    try:
        res, _ = run_pipeline(raw, message_id=str(num))
        is_ai = res.meta.fallback_used
        results.append({
            "NUM_SWIFT": num, "TAG": champ, "Confiance": res.meta.parse_confidence,
            "Mode_IA_Active": is_ai, "Nom": " ".join(res.name) if res.name else "",
            "Pays": res.country_town.country if res.country_town else "",
            "Raw": raw
        })
    except Exception as e:
        results.append({
            "NUM_SWIFT": num, "TAG": champ, "Confiance": 0.0,
            "Mode_IA_Active": False, "Nom": "ERROR", "Pays": "ERROR", "Raw": raw
        })
        
    if (i + 1) % 500 == 0:
        print(f"Progression : {i + 1} / {total} messages traités...")

out_df = pd.DataFrame(results)
out_df.to_excel("data/outputs/mt103_benchmark_FULL.xlsx", index=False)
print(f"Terminé ! Résultats complets sauvegardés dans data/outputs/mt103_benchmark_FULL.xlsx")
