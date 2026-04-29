import re

with open("src/e2_validator.py", "r") as f:
    e2_validator_content = f.read()

# Fix town ambiguity and fallback logic, specifically keeping track of the postal code
replacement = """
    # 2. ✅ Validation GeoNames PRIORITAIRE (si la ville existe, on la garde / la promeut)
    if GEONAMES_AVAILABLE and country and town_raw:
        is_valid, canonical, matched_via = validate_town_in_country(country, town_raw)
        
        # SI LA VILLE EST STRICTEMENT UN POSTAL CODE, LAISSEZ-LA PASSER EN E3
        if re.match(r"^([A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2})$", town_raw, flags=re.IGNORECASE) or re.match(r"^\d{4,6}$", town_raw):
             chosen_town = town_raw
             is_valid = False
             
        elif is_valid and matched_via and not is_town_literally_a_suburb:
"""

if "# 2. ✅ Validation GeoNames PRIORITAIRE" in e2_validator_content:
    if "SI LA VILLE EST STRICTEMENT UN POSTAL CODE" not in e2_validator_content:
        e2_validator_content = e2_validator_content.replace(
            "    # 2. ✅ Validation GeoNames PRIORITAIRE (si la ville existe, on la garde / la promeut)\n    if GEONAMES_AVAILABLE and country and town_raw:\n        is_valid, canonical, matched_via = validate_town_in_country(country, town_raw)\n        if is_valid and matched_via and not is_town_literally_a_suburb:",
            replacement
        )
        with open("src/e2_validator.py", "w") as f:
            f.write(e2_validator_content)
            print("Patched e2_validator town_raw logic.")
    else:
        print("Already Patched e2_validator.")
else:
    print("Cannot patch e2_validator.")
