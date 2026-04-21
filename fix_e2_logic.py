import re
with open("src/e2_validator.py", "r", encoding="utf-8") as f:
    content = f.read()

# Modification du booléen pour valider les ZI, BP, etc 
old_val = 'key_labels = {"road", "house_number", "unit", "po_box", "house"}'
new_val = 'key_labels = {"road", "house_number", "unit", "po_box", "house", "suburb", "city_district"}'
content = content.replace(old_val, new_val)

with open("src/e2_validator.py", "w", encoding="utf-8") as f:
    f.write(content)
