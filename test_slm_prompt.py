import requests
import json

payload = {
    "model": "qwen2.5:0.5b",
    "prompt": """TÂCHE: Extraire les informations d'un message SWIFT.
RÈGLES STRICTES:
FORMAT RÉPONSE (5 lignes):
name: <valeur>
address: <valeur ou ->
town: <valeur>
country: <XX>
postal: <valeur ou ->

---
Input: "JANE DOE\nRUE DE LA PAIX\nPARIS FRANCE"
Output:
name: JANE DOE
address: RUE DE LA PAIX
town: PARIS
country: FR
postal: -

Input: "/TN4839\nARIANA\navenue de l'uma La soukra\nSOCIETE MEUBLATEX SA\nATTN DIR FINANCIER"
Output:""",
    "stream": False,
    "options": {"temperature": 0.05}
}
try:
    r = requests.post("http://172.31.96.1:11434/api/generate", json=payload, timeout=5)
    print(r.json().get("response", "").strip())
except Exception as e:
    print(e)
