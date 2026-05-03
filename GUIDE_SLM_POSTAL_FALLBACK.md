# 🚀 Fallback SLM pour Inférence Postal — Documentation

## 📋 Vue d'ensemble

**Problème résolu:**
- Avant: Quand un code postal n'était pas dans le dictionnaire `postal_mappings.json`, la ville n'était pas inférée
- Après: Fallback intelligent au SLM (Ollama/LLM) pour les codes postaux non couverts

**Stratégie multi-niveaux:**

```
┌─────────────────────────────────────────────────────────┐
│ Entrée: Pays (TN) + Code Postal (9999) + Pas de Ville  │
└─────────────────────────────────────────────────────────┘
                          ⬇️
┌─────────────────────────────────────────────────────────┐
│ Niveau 1: Dictionnaire postal_mappings.json             │
│ Vitesse: ⚡ Très rapide (lookup O(1))                   │
│ Couverture: 20+ pays, ~100 codes postaux                │
└─────────────────────────────────────────────────────────┘
                   ⬇️ (Si pas trouvé)
┌─────────────────────────────────────────────────────────┐
│ Niveau 2: GeoNames Validation                           │
│ Valider le code postal avec la base GeoNames            │
│ Récupérer les villes principales du pays               │
└─────────────────────────────────────────────────────────┘
                   ⬇️ (Si pas trouvé)
┌─────────────────────────────────────────────────────────┐
│ Niveau 3: SLM Fallback (Ollama)                         │
│ Vitesse: 🐢 Lent (appel réseau)                         │
│ Couverture: Tous les pays (si modèle LLM adéquat)      │
│ Stratégie: Prompt + villes candidates → LLM → Réponse  │
└─────────────────────────────────────────────────────────┘
                          ⬇️
┌─────────────────────────────────────────────────────────┐
│ Résultat: Ville inférée (ou NULL si tous les niveaux échouent) │
└─────────────────────────────────────────────────────────┘
```

## 📁 Architecture des fichiers

### 1. `src/postal_slm_fallback.py` (NOUVEAU)
**Responsabilité:** Fallback SLM spécialisé pour codes postaux

```python
# Fonction principale
def infer_city_via_slm_postal(country_code, postal_code, model="phi3:mini") -> Optional[str]:
    """
    Inférer la ville depuis code postal via LLM.
    
    Processus:
    1. Récupérer les villes candidates de GeoNames
    2. Construire un prompt structuré pour le LLM
    3. Interroger Ollama
    4. Parser et valider la réponse
    5. Retourner la ville (ou None)
    """

# Fonction decision helper
def needs_postal_slm_fallback(country_code, postal_code, town) -> bool:
    """Décider si le fallback SLM doit être utilisé"""
```

### 2. `src/geonames/geonames_db.py` (MODIFIÉ)
**Nouvelles fonctions pour SLM:**

```python
def find_major_cities_by_country(country_code: str, limit: int = 10) -> list:
    """
    Récupérer les villes principales du pays (contexte pour SLM).
    
    Retourne:
        [
            {'name': 'TUNIS', 'population': 728453, ...},
            {'name': 'SFAX', 'population': 331440, ...},
            ...
        ]
    """

def infer_city_with_slm_candidate_info(country_code: str, postal_code: str) -> dict:
    """
    Préparer les informations candidates pour le SLM.
    
    Retourne:
        {
            'postal_code': '9999',
            'country_code': 'TN',
            'major_cities': [{'name': 'TUNIS', ...}, ...],
            'context': 'Tunisie: code postal 9999 [context]...'
        }
    """
```

### 3. `src/pipeline.py` (MODIFIÉ)
**Nouvelle logique dans `_enrich_city_via_postal()`:**

```python
def _enrich_city_via_postal(party):
    # 1. Essayer dictionnaire postal_mappings.json
    inferred_town = infer_city_from_postal_code(c, p)
    
    # 2. Si échoue, essayer SLM fallback
    if not inferred_town and needs_postal_slm_fallback(c, p, t):
        inferred_town = infer_city_via_slm_postal(c, p, model="phi3:mini")
        if inferred_town:
            party.meta.warnings.append(f"geo_postal_inference_slm_{c}:{p}→{inferred_town}")
    
    # 3. Appliquer l'inférence
    if inferred_town:
        party.country_town.town = inferred_town
```

## 🧪 Tests

### Test 1: Fonctions helpers (pas de dépendances externes)
```bash
python -c "
from src.geonames.geonames_db import find_major_cities_by_country
cities = find_major_cities_by_country('TN', limit=3)
print([c['name'] for c in cities])  # ['Tunis', 'Sfax', 'Sousse']
"
```

### Test 2: Tests avec Mock (sans Ollama)
```bash
python test_postal_slm_mock.py
```

Résultat attendu:
```
✅ TOUS LES TESTS RÉUSSIS AVEC MOCK!
```

### Test 3: Tests avec Ollama réel

#### 3.1. Démarrer Ollama
```bash
# Terminal 1: Démarrer Ollama
ollama serve

# Terminal 2: Charger un modèle (ou utiliser le modèle par défaut)
ollama pull phi3:mini
```

#### 3.2. Lancer les tests réels
```bash
python test_postal_slm_fallback.py
```

#### 3.3. Tester avec le pipeline complet
```bash
python -c "
from src.pipeline import run_pipeline

# Message SWIFT avec code postal non couvert
msg = ''':59:/FR99999
PARIS INC
RUE PRINCIPALE
99999
FRANCE'''

result, _ = run_pipeline(msg, disable_slm=False)
print(f'Ville: {result.country_town.town}')
print(f'Warnings: {result.meta.warnings}')
"
```

## 💡 Exemples d'utilisation

### Cas 1: Dictionnaire couvre le code postal
```python
from src.pipeline import run_pipeline

msg = """:59:/TN1000
COMPANY
RUE PRINCIPALE
1000
TUNISIE"""

result, _ = run_pipeline(msg)
print(result.country_town.town)  # "TUNIS"
print(result.meta.warnings)       # ['geo_postal_inference_TN:1000→TUNIS']
```

### Cas 2: Code postal non couvert → SLM fallback
```python
msg = """:59:/FR99999
COMPANY
RUE PRINCIPALE
99999
FRANCE"""

result, _ = run_pipeline(msg)
print(result.country_town.town)  # Dépend de la réponse SLM
print(result.meta.warnings)       # ['geo_postal_inference_slm_FR:99999→[VILLE]']
```

## 🔧 Configuration

### Modèle Ollama
```python
# Dans src/postal_slm_fallback.py, ligne ~17:
model: str = "phi3:mini"  # Modèle à utiliser

# Modèles alternatifs recommandés:
# - "phi3:mini" (léger, rapide)
# - "qwen2.5:0.5b" (très léger)
# - "llama2" (plus précis mais plus lent)
```

### Timeout Ollama
```python
# Dans src/config.py:
OLLAMA_TIMEOUT_SECONDS = 30
OLLAMA_MAX_RETRIES = 3
```

## 📊 Couverture

### Dictionnaire postal_mappings.json
```
TN: ~16 codes postaux
FR: ~18 codes postaux
GB: ~21 codes postaux
US: ~15 codes postaux
DE: ~10 codes postaux
CN: ~8 codes postaux
JP: ~10 codes postaux
...
Total: ~100+ codes postaux couverts
```

### SLM Fallback
```
Couverts: TOUS les pays (si Ollama + modèle disponibles)
Limitation: Dépend de la qualité du modèle LLM
```

## 🚨 Gestion des erreurs

### SLM indisponible (Ollama down)
```
1. log("GEO", "SLM postal fallback failed: [error]", level="WARN")
2. Retourner NULL
3. Continuer sans inférence postal
4. Pas d'impact sur le reste du pipeline
```

### Réponse SLM incohérente
```
1. Parser la réponse (première ligne)
2. Chercher dans les candidates (exact match)
3. Fallback: chercher match partiel
4. Si aucun match: retourner NULL
```

## 📈 Performance

| Étape | Temps | Condition |
|-------|--------|-----------|
| Dictionnaire lookup | ~1ms | Toujours |
| GeoNames query | ~10ms | Si dict échoue |
| SLM LLM call | ~500ms-5s | Si dict+GeoNames échouent |
| **Total (best case)** | ~1ms | Code postal dans dict |
| **Total (worst case)** | ~5s | SLM fallback complet |

## 🎯 Points clés

1. **Stratégie intelligente:** Essayer d'abord le dictionnaire (rapide) avant SLM (lent)
2. **Couverture complète:** Tous les pays supportés par GeoNames + Ollama
3. **Fallback robuste:** Gestion d'erreurs à chaque niveau
4. **Warnings transparents:** Traçabilité de l'inférence (dictionnaire vs SLM)
5. **Tests complets:** Mock tests sans dépendances, tests réels avec Ollama

## 🔗 Intégration dans le pipeline

```
E0 (Preprocess) → E1 (Parse) → E2 (Validate) → E2.5 (Fragment)
                                        ⬇️
                            _enrich_city_via_postal() ← NOUVEAU
                            (Dict → SLM fallback)
                                        ⬇️
E3 (SLM Fallback general) → OUTPUT
```

La fonction `_enrich_city_via_postal()` est appelée AVANT le SLM général (E3), assurant que les inférences de base sont toujours tentées d'abord.

## 📝 Logs

### Log dictionnaire réussi
```
geo_postal_inference_TN:1000→TUNIS
```

### Log SLM fallback réussi
```
geo_postal_inference_slm_FR:13000→MARSEILLE
```

### Log erreur SLM
```
[GEO] SLM postal fallback failed: Connection refused (WARN)
```

---

**Last updated:** 2024
**Status:** ✅ Implémenté et testé
