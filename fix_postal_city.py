import re

def enrichir_ville_par_code_postal(town, postal_code, country_code):
    # Simulation d'un mini-dictionnaire ou d'un appel API/GeoNames
    # Dans une vraie BDD (comme GeoNames que vous avez), on ferait une vraie requête.
    postal_to_city_tn = {
        "2037": "ENNASR / ARIANA",
        "1000": "TUNIS",
        "2080": "ARIANA",
        "3000": "SFAX",
        "4000": "SOUSSE",
        "8000": "NABEUL"
    }
    
    if country_code == "TN" and postal_code:
        # Nettoyage
        clean_code = re.sub(r"[^\d]", "", str(postal_code))
        if clean_code in postal_to_city_tn:
            if not town or town.strip() == "" or town.lower() == "none":
                return postal_to_city_tn[clean_code]
    return town

# Test logic
t = None
c = "TN"
p = "2037"
print(f"Code Postal: {p}, Pays: {c}")
t = enrichir_ville_par_code_postal(t, p, c)
print(f"Ville Déduite via Code Postal: {t}")
