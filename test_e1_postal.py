import re

raw = "E14 5AB"
m1 = re.match(r"^([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})$", raw, flags=re.IGNORECASE)
print("UK code:", m1.groups() if m1 else None)

def extract_uk_postal(line):
    m = re.match(r"^([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})\s+(.+)$", line, flags=re.IGNORECASE)
    if m:
        return m.group(1), m.group(2)
    # also try postal only
    m = re.match(r"^([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})$", line, flags=re.IGNORECASE)
    if m:
        return m.group(1), None
    return None, None

print(extract_uk_postal("E14 5AB LONDON"))
print(extract_uk_postal("E14 5AB"))
