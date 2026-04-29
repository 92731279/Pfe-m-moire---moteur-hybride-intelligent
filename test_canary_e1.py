import re
raw = "E14 5AB"
m = re.match(r"^([A-Z]{1,2}\d[A-Z\d]?)\s*(\d[A-Z]{2})$", raw, flags=re.IGNORECASE)
print(m.groups() if m else None)
