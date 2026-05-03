import pandas as pd
import time
import os

from src.pipeline import run_pipeline
from src.iso20022_mapper import build_iso20022_party_payload

def compare_field(predicted: str, truth: str) -> bool:
    if pd.isna(truth) or truth == "":
        return True # Si pas de verite terrain, on compte juste
    if pd.isna(predicted) or predicted is None:
        return False
    return str(truth).strip().upper() in str(predicted).strip().upper()

def evaluate_golden(csv_path: str):
    if not os.path.exists(csv_path):
        print(f"[!] Erreur: Fichier Golden Dataset {csv_path} introuvable.")
        print("Veuillez creer un CSV avec colonnes: RAW, TRUTH_NAME, TRUTH_COUNTRY, TRUTH_TOWN, TRUTH_PSTCD")
        return

    df = pd.read_csv(csv_path, sep=";")
    print(f"[+] Golden Dataset charge: {len(df)} cas de test annotees.")

    results = []

    for i, row in df.iterrows():
        raw = str(row['RAW'])
        print(f"--- Evaluation {i+1}/{len(df)} ---")
        
        # Scenario 1: Rules Only
        t0 = time.time()
        res_rules, _ = run_pipeline(raw, disable_slm=True)
        t_rules = time.time() - t0
        iso_rules = build_iso20022_party_payload(res_rules)
        
        # Scenario 2: Hybrid (Rules + SLM Fallback)
        t0 = time.time()
        res_hybrid, _ = run_pipeline(raw, disable_slm=False, slm_model="qwen2.5:0.5b")
        t_hybrid = time.time() - t0
        iso_hybrid = build_iso20022_party_payload(res_hybrid)
        
        # Extraction ISO representations
        def extract_iso_fields(iso):
            pstl = iso.get("PstlAdr", {})
            return {
                "name": iso.get("Nm", ""),
                "country": pstl.get("Ctry", ""),
                "town": pstl.get("TwnNm", ""),
                "postal": pstl.get("PstCd", ""),
                "address": " ".join(pstl.get("AdrLine", []))
            }
        
        fields_r = extract_iso_fields(iso_rules)
        fields_h = extract_iso_fields(iso_hybrid)
        
        truth = {
            "name": row.get('TRUTH_NAME', ""),
            "country": row.get('TRUTH_COUNTRY', ""),
            "town": row.get('TRUTH_TOWN', ""),
            "postal": row.get('TRUTH_PSTCD', "")
        }
        
        results.append({
            "ID": i+1,
            "Rules_Time_ms": int(t_rules * 1000),
            "Hybrid_Time_ms": int(t_hybrid * 1000),
            "SLM_Triggered": res_hybrid.meta.fallback_used,
            
            "Rules_Name_Match": compare_field(fields_r["name"], truth["name"]),
            "Rules_Ctry_Match": compare_field(fields_r["country"], truth["country"]),
            "Rules_Town_Match": compare_field(fields_r["town"], truth["town"]),
            
            "Hybrid_Name_Match": compare_field(fields_h["name"], truth["name"]),
            "Hybrid_Ctry_Match": compare_field(fields_h["country"], truth["country"]),
            "Hybrid_Town_Match": compare_field(fields_h["town"], truth["town"]),
        })

    summary = pd.DataFrame(results)
    
    total = len(summary)
    print("\n" + "="*50)
    print("Rapport Qualite et Evaluation - A/B Testing")
    print("="*50)
    print(f"Total cas de tests : {total}")
    print(f"Taux d'activation SLM : {summary['SLM_Triggered'].mean()*100:.1f}%")
    print(f"Temps de traitement moyen (Regles seules) : {summary['Rules_Time_ms'].mean():.1f} ms")
    print(f"Temps de traitement moyen (Hybride SLM)   : {summary['Hybrid_Time_ms'].mean():.1f} ms")
    print("\n" + "Accuracy par Champ (Regles  ->  Hybride)")
    print(f"Name     : {summary['Rules_Name_Match'].mean()*100:.1f}%  ->  {summary['Hybrid_Name_Match'].mean()*100:.1f}%")
    print(f"Country  : {summary['Rules_Ctry_Match'].mean()*100:.1f}%  ->  {summary['Hybrid_Ctry_Match'].mean()*100:.1f}%")
    print(f"TownNm   : {summary['Rules_Town_Match'].mean()*100:.1f}%  ->  {summary['Hybrid_Town_Match'].mean()*100:.1f}%")
    print("="*50)
    
    os.makedirs("data/outputs", exist_ok=True)
    summary.to_csv("data/outputs/golden_benchmark_results.csv", sep=";", index=False)
    print("Export detaille sauvegarde dans data/outputs/golden_benchmark_results.csv")

if __name__ == "__main__":
    # Mocking un petit fichier pour l'exemple (normalement ce sera rempli par le metier)
    mock_csv = "data/golden_dataset.csv"
    if not os.path.exists(mock_csv):
        print("[!] Creation d'un Golden Dataset fictif (mock) pour demo...")
        with open(mock_csv, "w") as f:
            f.write("RAW;TRUTH_NAME;TRUTH_COUNTRY;TRUTH_TOWN;TRUTH_PSTCD\n")
            f.write(":59:\\n/123456789\\nJHON DOE\\nSTREET 45 NEW YORK\\nUSA;JHON DOE;US;NEW YORK;\n")
            f.write(":50K:\\nABC COMPANY\\nRUE DE LA REPUBLIQUE\\nTUNIS TUNISIA;ABC COMPANY;TN;TUNIS;\n")
            f.write(":59:\\n/0987654321\\nSOCIETE GENERALE\\nZ.I CHERGUIA\\nARIANA;SOCIETE GENERALE;TN;ARIANA;\n")
            
    evaluate_golden(mock_csv)
