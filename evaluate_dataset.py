import pandas as pd
from src.pipeline import run_pipeline
import json

def process_swift_excel():
    print("Chargement du dataset Excel...")
    df = pd.read_excel('data/MT103.xls')
    
    # Ils utilisent 'F50K', 'F59' dans ce fichier
    target_fields = ['F50K', 'F59', 'F50F', 'F59F', '50K', '59', '50F', '59F']
    df_parties = df[df['CHAMPS'].isin(target_fields)].dropna(subset=['VALEUR'])
    
    results = []
    
    print(f"Évaluation de {len(df_parties)} lignes...")
    
    for i, row in df_parties.iterrows():
        raw_val = str(row['VALEUR'])
        field = row['CHAMPS'].replace('F', '') # F50K -> 50K
        raw_message = f":{field}:{raw_val}"
        
        result, logger = run_pipeline(raw_message, message_id=str(row['NUM_SWIFT']))
        
        results.append({
            'NUM_SWIFT': row['NUM_SWIFT'],
            'CHAMPS': field,
            'VALEUR_BRUTE': raw_val,
            'TOWN': result.country_town.town if result.country_town else None,
            'COUNTRY': result.country_town.country if result.country_town else None,
            'CONFIDENCE': result.meta.parse_confidence,
            'REJECTED': result.meta.rejected,
            'WARNINGS': " | ".join(result.meta.warnings)
        })
        
    if not results:
        print("Aucune ligne correspondante trouvée.")
        return
        
    df_results = pd.DataFrame(results)
    
    df_failed = df_results[(df_results['REJECTED'] == True) | (df_results['CONFIDENCE'] < 0.8)]
    df_success = df_results[(df_results['REJECTED'] == False) & (df_results['CONFIDENCE'] >= 0.8)]
    
    df_failed.to_csv("data/outputs/analyse_echecs.csv", index=False, sep=";")
    df_results.to_csv("data/outputs/evaluation_complete.csv", index=False, sep=";")
    
    print(f"Terminé ! Total évalué : {len(df_results)}")
    print(f"Succès E1/E2 directs: {len(df_success)} | Échecs / Ambigus (Vers SLM) : {len(df_failed)}")
    print("Rapports générés dans `data/outputs/analyse_echecs.csv`.")

if __name__ == '__main__':
    process_swift_excel()
