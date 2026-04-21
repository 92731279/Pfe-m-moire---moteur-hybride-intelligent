import pandas as pd
df = pd.read_excel('data/outputs/mt103_benchmark_100.xlsx')
failures = df[df['Besoin_IA'] == True]

print(f"Total des msgs: {len(df)}")
print(f"Rejetés par l'heuristique (E1/E2 implorent E3 IA): {len(failures)} sur {len(df)}")

print("\n--- TOP CAS À ÉTUDIER ---")
for idx, row in failures.head(5).iterrows():
    print(f"\n[SWIFT {row['NUM_SWIFT']} - TAG {row['TAG']}]")
    print(f"RAW:\n{row['Raw Reconstruit']}")
    print(f"Warnings: {row['Warnings (Pourquoi ça a échoué)']}")
