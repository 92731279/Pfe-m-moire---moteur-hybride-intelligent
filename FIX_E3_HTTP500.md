# Fix - Erreurs HTTP 500 SLM E3

## Problème rencontré
```
[E3] HTTP 500
[E3] SLM a échoué, conservation du résultat original
```

Cette erreur survient quand Ollama retourne des erreurs HTTP 500 lors des appels à `/api/generate`.

---

## Causes identifiées

| Cause | Symptôme | Solution |
|-------|----------|----------|
| **Ollama surchargé** | Erreurs intermittentes 500 | Circuit breaker + backoff |
| **Timeout du modèle** | Appels qui durent trop longtemps | Réduire `num_predict` + augmenter timeout |
| **Appels concurrents** | Pics d'erreurs lors de plusieurs analyses | Limiter retries |
| **Modèle pas prêt** | Erreur au 1er appel | Pré-charger le modèle |

---

## Solutions implémentées

### 1. ✅ Circuit Breaker
Classe `OllamaCircuitBreaker` qui:
- Compte les erreurs consécutives
- "Coupe le circuit" après 2 erreurs
- Attend 20 secondes avant de réessayer
- Évite de surcharger davantage Ollama

**Code:**
```python
if not _ollama_circuit_breaker.can_attempt():
    logger.warning("[E3] Circuit breaker OUVERT - SLM désactivé temporairement")
    return None
```

### 2. ✅ Backoff exponentiel
Délais d'attente entre retries:
- 1ère retry: 2 secondes
- 2ème retry: 4 secondes
- Maximum: 5 secondes

**Bénéfice:** Ollama a du temps pour récupérer

### 3. ✅ Réduction progressive du prompt
Si erreur, réduit `num_predict` de 30:
- Tentative 1: 120 tokens
- Tentative 2: 90 tokens
- Tentative 3: 60 tokens

**Bénéfice:** Prompts plus courts = plus rapides

### 4. ✅ Logging amélioré
Messages détaillés pour déboguer:
```
[E3] HTTP 500 (tentative 1/2)
[E3] Attente 2s avant retry...
[E3] Circuit breaker OUVERT après 2 erreurs
```

---

## Comment utiliser

### Avant (version ancienne)
```python
e2 = apply_slm_fallback(e2, model=slm_model)  # HTTP 500 → crash
```

### Après (version fixée)
```python
e2 = apply_slm_fallback(e2, model=slm_model)  # HTTP 500 → retry + fallback gracieux
```

Les erreurs sont maintenant **gérées automatiquement** sans intervention.

---

## Diagnostic et test

### 1. Vérifier Ollama
```bash
curl -s http://172.31.96.1:11434/api/tags | jq '.models[].name'
```

Doit retourner: `phi3:mini`

### 2. Tester le modèle
```bash
python3 test_ollama.py
```

Doit retourner: `✅ /api/generate → 200`

### 3. Pré-charger le modèle (optionnel mais recommandé)
```bash
# Force Ollama à charger phi3:mini en mémoire
curl -X POST http://172.31.96.1:11434/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "model": "phi3:mini",
    "prompt": "test",
    "stream": false,
    "options": {"num_predict": 5}
  }'
```

### 4. Relancer Streamlit
```bash
source .venv/bin/activate
streamlit run app/streamlit_app2.py
```

---

## Comportement attendu après fix

### Scénario 1: Ollama accessible
```
✅ GeoNames disponible pour validation
[E3] Appel SLM en cours
[E3] SLM réponse en 2.5s
[E3] SLM terminé
```

### Scénario 2: Ollama temporairement indisponible
```
[E3] HTTP 500 (tentative 1/2)
[E3] Attente 2s avant retry...
[E3] HTTP 500 (tentative 2/2)
[E3] Circuit breaker OUVERT après 2 erreurs
[E3] SLM a échoué, conservation du résultat original
```
→ **Application continue à fonctionner**

### Scénario 3: Ollama récupère
```
[E3] Circuit breaker tentative de FERMETURE
[E3] SLM réponse en 1.8s
[E3] SLM terminé
```
→ **Retour à la normale**

---

## Paramètres configurables

Modifier dans `src/e3_slm_fallback.py`:

```python
# Circuit breaker settings
_ollama_circuit_breaker = OllamaCircuitBreaker(
    failure_threshold=2,      # Erreurs avant ouverture (2 ou 3)
    recovery_timeout=20       # Secondes de pause (10-30)
)

# Retry settings
self.max_retries = 2  # Retries (1-3)
self.timeout = 120    # Timeout total en secondes (60-180)
```

**Recommandations:**
- `failure_threshold=2`: Strict, protège bien Ollama
- `recovery_timeout=20`: Assez long pour que le modèle se rétablisse
- `max_retries=2`: 3 tentatives total, pas trop long

---

## Fichiers modifiés

✅ [src/e3_slm_fallback.py](src/e3_slm_fallback.py)
- Ajout classe `OllamaCircuitBreaker`
- Amélioration `_call_slm_optimized()` avec backoff + circuit breaker
- Logging détaillé

---

## Monitoring

Pour surveiller les performances SLM:

```python
from src.e3_slm_fallback import E3SLMFallback

# Après plusieurs appels:
stats = E3SLMFallback.get_cache_stats()
print(f"Cache: {stats['hits']} hits, {stats['misses']} misses")
print(f"Hit rate: {stats['hit_rate_percent']}%")
```

---

## FAQ

**Q: Pourquoi encore des erreurs après le fix?**  
A: Le circuit breaker laisse Ollama se reposer. Les erreurs sont normales s'il y a vraiment un problème Ollama. Relancer Ollama si nécessaire.

**Q: Est-ce que ça ralentit l'app?**  
A: Oui, légèrement (~2-5s de backoff). Mais mieux que de crasher!

**Q: Comment désactiver le circuit breaker?**  
A: Augmenter `failure_threshold` à 999 dans `e3_slm_fallback.py`

**Q: Ollama a crashé, comment récupérer?**  
A: Attendre 20-30 secondes (le circuit breaker réessaiera automatiquement) ou relancer Streamlit.

---

## Version

- 📝 Date: 2026-04-17
- 🔧 Fix Version: 1.0
- ⚙️ Ollama: 0.20.7+
- 🐍 Python: 3.10+
