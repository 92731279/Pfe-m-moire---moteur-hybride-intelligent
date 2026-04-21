import pdfplumber

with pdfplumber.open("data/des msgs reelles.pdf") as pdf:
    text = ""
    for page in pdf.pages:
         text += page.extract_text() + "\n---PAGE---\n"
print(text[:2000])
