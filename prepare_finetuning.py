import pandas as pd
import json
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="bs4")
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

def generate_dataset():
    print("Chargement de MT103.xls pour générer le dataset de Fine-Tuning...")
    df = pd.read_excel("data/MT103.xls")
    df_parties = df[df["CHAMPS"].isin(["F50K", "F50F", "F59", "F59F"])]
    grouped = df_parties.groupby(["NUM_SWIFT", "CHAMPS"])
    
    dataset = []
    print(f"{len(grouped)} messages à traiter. Filtrage des cas 'parfaits' pour l'apprentissage...")
    
    system_prompt = """TÂCHE: Extraire les informations d'un message SWIFT.
RÈGLES STRICTES:
1. name = UNIQUEMENT nom personne ou entreprise
2. address = rue/numéro/PO BOX/bâtiment
3. town = ville SEULE
4. country = code ISO 2 lettres uniquement
5. postal = code postal ou - si absent"""

    count = 0
    # On limite à 500 pour la démonstration/génération rapide
    for (num, champ), group in grouped:
        if count >= 500: break
        raw = build_raw_message(group)
        
        # Astuce : On utilise l'heuristique (E1/E2) quand elle est sûre d'elle (>0.85)
        # pour "enseigner" à l'IA la bonne réponse (Self-Instruct / Distillation)
        try:
            res, _ = run_pipeline(raw, message_id=f"FT_{num}")
            if res.meta.parse_confidence >= 0.80:
                # C'est un bon exemple pour l'entraînement !
                name = " ".join(res.name) if res.name else "UNKNOWN"
                address = " ".join(res.address_lines) if res.address_lines else "-"
                town = res.country_town.town if res.country_town and res.country_town.town else "-"
                country = res.country_town.country if res.country_town and res.country_town.country else "-"
                postal = res.country_town.postal_code if res.country_town and res.country_town.postal_code else "-"
                
                output_text = f"name: {name}\naddress: {address}\ntown: {town}\ncountry: {country}\npostal: {postal}"
                
                # Format OpenAI JSONL (utilisé pour fine-tuner Qwen, LLaMA, etc.)
                conversation = {
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Input: \"{raw}\""},
                        {"role": "assistant", "content": output_text}
                    ]
                }
                dataset.append(conversation)
        except Exception:
            pass
        count += 1
        
    out_file = "data/outputs/qwen_finetuning_dataset.jsonl"
    with open(out_file, "w", encoding="utf-8") as f:
        for item in dataset:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            
    print(f"\nTerminé ! {len(dataset)} exemples de haute qualité générés dans {out_file}")
    
if __name__ == "__main__":
    generate_dataset()
