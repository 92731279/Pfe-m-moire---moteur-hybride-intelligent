# Moteur Hybride SWIFT → ISO 20022

**Projet PFE — Master 2 Ingénierie des Systèmes d'Information et Data Science**

Auteure : Wided

---

## Objectif

Transformer des messages SWIFT de paiement (champs `50F/K` et `59F/-`) vers le format canonique ISO 20022 (debtor/creditor), en combinant règles métier, libpostal et SLM local.

---

## Architecture du pipeline

```
Message SWIFT brut
        │
        ▼
E0 — Prétraitement
(Nettoyage, normalisation, extraction IBAN, détection type entité)
        │
        ▼
E1 — Parsing
(Extraction des champs : nom, adresse, pays, ville)
→ Support : 50K (libre) / 59 (structuré)
        │
        ▼
E2 — Validation sémantique (2 passes)
Pass 1 :
- Validation country / town (GeoNames)
- Résolution ambiguïté (ville vs suburb)

Pass 2 :
- Validation adresse (libpostal)
- Cohérence géographique (adresse ↔ ville ↔ pays)
        │
        ▼
E2.5 — Fragmentation ISO 20022
- Mapping vers format structuré :
  (StrtNm, BldgNb, TwnNm, Ctry…)
- Fallback AdrLine si info insuffisante
        │
        ▼
(si ambigu ou incohérent)
        ▼
E3 — SLM Fallback (Ollama)
- Modèles : phi3:mini / qwen2.5:0.5b
- Réinterprétation du message
- Réinjection dans pipeline (revalidation E2)
        │
        ▼
Décision métier
- Accepté
- Confiance faible (manual review)
- Rejet (quarantaine)
        │
        ▼
JSON canonique final (ISO 20022)
```

---

## Structure du projet

```
moteur_hybride2/
├── app/
│   └── streamlit_app.py          # Interface Streamlit
├── data/
│   ├── reference/                # Référentiels JSON
│   │   ├── address_keywords.json
│   │   ├── capitals.json
│   │   ├── cities_by_country.json
│   │   ├── country_aliases.json
│   │   ├── org_hints.json
│   │   └── swift_party_id_codes.json
│   ├── geonames/
│   │   ├── db/                   # Base SQLite GeoNames
│   │   └── raw/                  # Fichiers bruts GeoNames
│   ├── outputs/
│   ├── samples/
│   └── kb/
├── src/
│   ├── geonames/
│   │   ├── geonames_db.py        # Accès SQLite GeoNames
│   │   └── geonames_loader.py    # Chargement GeoNames
│   ├── config.py
│   ├── models.py                 # Structures de données (Pydantic)
│   ├── logger.py
│   ├── pipeline_logger.py
│   ├── reference_data.py         # Chargement référentiels
│   ├── e0_preprocess.py          # Étape E0
│   ├── e1_parser.py              # Étape E1
│   ├── e2_address_parser.py      # libpostal wrapper
│   ├── e2_validator.py           # Étape E2
│   ├── e3_slm_fallback.py        # Étape E3
│   ├── pipeline.py               # Orchestration
│   ├── ambiguity_resolver.py
│   └── toponym_normalizer.py
└── tests/
    ├── test_e0.py
    ├── test_e1_free.py
    ├── test_e1_structured.py
    ├── test_e2.py
    ├── test_e2_address_parser.py
    ├── test_e3.py
    └── test_pipeline.py
```

---

## Installation

```bash
# Créer environnement virtuel
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
.venv\Scripts\activate      # Windows

# Installer dépendances
pip install pydantic streamlit postal

# Lancer Streamlit
streamlit run app/streamlit_app.py

# Lancer les tests
python -m pytest tests/ -v
```

---

## Configuration SLM (Ollama)

```bash
# Installer Ollama et télécharger le modèle
ollama pull phi3:mini

# Vérifier que Ollama tourne
curl http://localhost:11434/api/tags
```

L'URL Ollama est configurable dans `src/config.py` :
```python
OLLAMA_BASE_URL = "http://172.31.96.1:11434"
OLLAMA_MODEL = "phi3:mini"
```

---

## Exemple d'utilisation

```python
from src.pipeline import run_pipeline

raw = """:50K:/FR7630006000011234567890189
JANE DOE RUE DE LA REPUBLIQUE
PARIS FRANCE
"""

result, logger = run_pipeline(raw, message_id="MSG_TEST", slm_model="phi3:mini")
print(result.model_dump())
```

---

## Technologies

- **Python 3.11+**
- **Pydantic** — modèles de données
- **libpostal** — parsing d'adresses universel
- **GeoNames** — base géographique mondiale (SQLite)
- **Ollama + phi3:mini** — SLM local pour cas ambigus
- **Streamlit** — interface de démonstration
- **pytest** — tests unitaires
