import pandas as pd
from typing import List, Dict
import warnings

# Ignorer les warnings liés au format XLS
warnings.filterwarnings("ignore", category=UserWarning, module="bs4")

from src.pipeline import run_pipeline

def build_raw_message(group: pd.DataFrame) -> str:
    """Reconstruit le message SWIFT hybride à partir des sous-champs de la base."""
    # On s'assure que c'est trié par ordre d'apparition
    group = group.sort_values(by="ORDRE")
    
    # Extraire le tag (Ex: 'F50K' -> '50K')
    champ = str(group.iloc[0]["CHAMPS"]).replace('F', '', 1)
    
    lines = [f":{champ}:"]
    
    for _, row in group.iterrows():
        sc = str(row["SOUS_CHAMPS"]).upper()
        val = str(row["VALEUR"])
        if val == "nan": continue
        
        if sc == "COMPTE":
            # Ajouter le compte sur la première ligne
            lines[0] += ("/" + val if not val.startswith("/") else val)
        else:
            lines.append(val)
            
    return "\n".join(lines)

def run_benchmark():
    print("Chargement de data/MT103.xls...")
    try:
        # Lire le fichier en ignorant les warnings OLE2
        df = pd.read_excel("data/MT103.xls")
    except Exception as e:
        print(f"Erreur de lecture du XLS : {e}")
        return

    # Filtrer uniquement les champs de parties pertinentes (50K, 50F, 59, 59F)
    df_parties = df[df["CHAMPS"].isin(["F50K", "F50F", "F59", "F59F"])]
    
    # Grouper par message et par champ
    grouped = df_parties.groupby(["NUM_SWIFT", "CHAMPS"])
    
    print(f"{len(grouped)} parties de messages identifiées dans le fichier.")
    
    # On va tester les 100 premiers cas pour être rapide et avoir un diagnostic immédiat
    limite = 100
    print(f"Lancement du moteur Moteur Hybride sur les {limite} premiers cas...")
    
    results = []
    count = 0
    
    for (num_swift, champ), group in grouped:
        if count >= limite:
            break
        
        raw_msg = build_raw_message(group)
        msg_id = f"MSG_{num_swift}_{champ}"
        
        try:
            res, _ = run_pipeline(raw_msg, message_id=msg_id)
            meta = res.meta
            
            needs_ia = meta.parse_confidence < 0.85
            
            results.append({
                "NUM_SWIFT": num_swift,
                "TAG": champ,
                "Confiance": meta.parse_confidence,
                "Besoin_IA": "OUI" if needs_ia else "NON",
                "Ville_detectee": res.country_town.town if res.country_town else "",
                "Pays_detecte": res.country_town.country if res.country_town else "",
                "Warnings (Pourquoi ça a échoué)": " | ".join(meta.warnings),
                "Raw Reconstruit": raw_msg.replace('\n', ' \\n ')
            })
        except Exception as e:
            results.append({
                "NUM_SWIFT": num_swift,
                "TAG": champ,
                "Confiance": 0.0,
                "Besoin_IA": "ERREUR",
                "Ville_detectee": "",
                "Pays_detecte": "",
                "Warnings (Pourquoi ça a échoué)": str(e),
                "Raw Reconstruit": raw_msg.replace('\n', ' \\n ')
            })
        
        count += 1
        if count % 20 == 0:
            print(f"... {count}/{limite} traités")

    out_df = pd.DataFrame(results)
    
    # Analyse
    perfect = len(out_df[out_df["Confiance"] >= 0.85])
    ambiguous = len(out_df) - perfect
    
    print("\n--- RÉSULTATS DU BENCHMARK MT103 (Échantillon de 100) ---")
    print(f"Parfait sans IA (>= 85%) : {perfect} ({perfect/limite * 100:.1f}%)")
    print(f"Rejeté / Envoyé à l'IA (< 85%) : {ambiguous} ({ambiguous/limite * 100:.1f}%)")
    
    out_path = "data/outputs/mt103_benchmark_100.xlsx"
    out_df.to_excel(out_path, index=False)
    print(f"\nRapport détaillé sauvé dans : {out_path}")
    
    print("\n--- TOP 3 ÉCHECS LES PLUS COURANTS ---")
    echoues = out_df[out_df["Besoin_IA"] == "OUI"]
    print(echoues[["NUM_SWIFT", "Confiance", "Ville_detectee", "Warnings (Pourquoi ça a échoué)"]].head(3).to_string())

if __name__ == "__main__":
    run_benchmark()
