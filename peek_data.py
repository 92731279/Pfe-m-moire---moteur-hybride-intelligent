import pandas as pd

try:
    df = pd.read_excel("data/MT103.xls", nrows=5)
    print("Cols:", df.columns.tolist())
    print("Shape:", df.shape)
    for index, row in df.iterrows():
        print(f"\nRow {index}:")
        for col in df.columns:
            if str(row[col]) != "nan":
                print(f"  {col}: {str(row[col])[:100]}")
except Exception as e:
    print(f"Error: {e}")
