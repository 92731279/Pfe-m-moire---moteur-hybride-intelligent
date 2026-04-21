import pandas as pd

try:
    df = pd.read_excel("data/outputs/mt103_benchmark_100.xlsx")
    
    # Filtrer ceux qui ont été rejetés par l'heuristique (nécessitant E3)
    # ou dont le parsing a échoué (confiance faible)
    failures = df[df["STATUS"] != "E1_E2_SUCCESS"]
    
    print(f"Total des messages analysés : {len(df)}")
    print(f"Messages échouant l'étape Heuristique (E1/E2) : {len(failures)} ({len(failures)/len(df)*100:.1f}%)")
    
    print("\n=== TOP 5 PIRES CAS (NÉCESSITANT L'IA OU ÉCHOUÉS) ===")
    count = 0
    for idx, row in failures.iterrows():
        if count >= 5: break
        print(f"\n[Message ID]: {row['MESSAGE_ID']}")
        print(f"[RAW]:\n{row['RAW_TEXT']}")
        print(f"[STATUS]: {row.get('STATUS', 'UNKNOWN')}")
        count += 1
except Exception as e:
    print(f"Erreur lors de l'analyse : {e}")
