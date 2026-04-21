import pdfplumber

with pdfplumber.open("data/des msgs reelles.pdf") as pdf:
    for i, page in enumerate(pdf.pages[:2]):
        print(f"--- Page {i} ---")
        print(page.extract_text())
