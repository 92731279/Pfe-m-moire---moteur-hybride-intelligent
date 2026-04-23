import requests

def infer_geo_slm(country, town=None, postal_code=None, slm_model="qwen2.5:0.5b"):
    prompt = f"""Tu es un expert géographique exact en codes postaux et villes.
Règles strictes :
1. Si je te donne une ville et le pays, renvoie UNIQUEMENT le code postal principal associé (4 à 5 chiffres).
2. Si je te donne un code postal et le pays, renvoie UNIQUEMENT le nom de la ville correspondante en majuscules.
3. Ne justifie pas, n'ajoute pas de texte, renvoie UNIQUEMENT la valeur demandée.

Pays : {country}
Ville : {town if town else '?'}
Code Postal : {postal_code if postal_code else '?'}
La valeur manquante est (répond par son nom/valeur sans espace ni ponctuation): """
    
    try:
        r = requests.post("http://172.31.96.1:11434/api/generate", json={
            "model": slm_model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.0}
        }, timeout=5)
        res = r.json().get("response", "").strip()
        print(f"SLM reponse for {town} {postal_code}: {res}")
        return res
    except Exception as e:
        print(e)
        return None

infer_geo_slm("TUNISIE", town="SUKRAH")
infer_geo_slm("TUNISIE", postal_code="2080")
