import re

with open("src/e1_parser.py", "r") as f:
    content = f.read()

# we will add UK postal code matching rules
uk_postal_rule = r"""

    # 6. UK Postal Code: E14 5AB LONDON or LONDON E14 5AB
    # Easiest way is to match postal code alone or with town
    m = re.match(r"^([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})\s+([A-Z][A-Z0-9()' .\-]+)$", raw, flags=re.IGNORECASE)
    if m:
        pc = m.group(1) + " " + m.group(2)
        town = _clean_town_value(_norm(m.group(3)))
        if town and not _contains_address_keyword(town): return 0, len(raw), CountryTown(country=None, town=town, postal_code=pc)

    m = re.match(r"^([A-Z][A-Z0-9()' .\-]+)\s+([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})$", raw, flags=re.IGNORECASE)
    if m:
        town = _clean_town_value(_norm(m.group(1)))
        pc = m.group(2) + " " + m.group(3)
        if town and not _contains_address_keyword(town): return 0, len(raw), CountryTown(country=None, town=town, postal_code=pc)
        
    m = re.match(r"^([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})$", raw, flags=re.IGNORECASE)
    if m:
        pc = _norm(m.group(1))
        return 0, len(raw), CountryTown(country=None, town=None, postal_code=pc)
"""

if "# 5. Postal seul: 38100 GRENOBLE" in content:
    content = content.replace("    return None\ndef _apply_iban", uk_postal_rule + "\n    return None\ndef _apply_iban")
    with open("src/e1_parser.py", "w") as f:
        f.write(content)
        print("Done patching.")
else:
    print("Could not patch.")
