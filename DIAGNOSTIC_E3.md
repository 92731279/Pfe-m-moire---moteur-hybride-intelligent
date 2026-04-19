# Diagnostic - Erreurs HTTP 500 du SLM E3

## Problème
L'application Streamlit affiche: `[E3] HTTP 500` et `[E3] SLM a échoué, conservation du résultat original`

## Causes potentielles

### 1. Ollama sous charge / Modèle surchargé
- **Symptômes**: Erreurs HTTP 500 intermittentes
- **Cause**: Trop d'appels concurrents à Ollama ou modèle qui crash
- **Solution**: Limiter les retries, ajouter de l'attente entre appels

### 2. Timeout de réponse du modèle
- **Symptômes**: La requête prend trop longtemps
- **Cause**: Le modèle `phi3:mini` est lent ou surchargé
- **Solution**: Réduire `num_predict`, augmenter le timeout initial

### 3. Malformation du payload JSON
- **Symptômes**: Erreurs 500 systématiques
- **Cause**: Options invalides envoyées à Ollama
- **Solution**: Valider le payload avant envoi

### 4. Modèle pas chargé
- **Symptômes**: Erreur 500 au premier appel
- **Cause**: Le modèle `phi3:mini` n'est pas en mémoire
- **Solution**: Pré-charger le modèle avec un test

## Tests à effectuer

```bash
# 1. Vérifier Ollama
curl -s http://172.31.96.1:11434/api/tags | jq '.models[].name'

# 2. Tester le modèle directement
python3 test_ollama.py

# 3. Vérifier les ressources
free -h  # Mémoire disponible
ps aux | grep ollama  # Processus Ollama
```

## Solutions à appliquer

1. **Réduire la complexité du prompt** → Plus rapide
2. **Augmenter le retry delay** → Laisser Ollama respirer
3. **Implémenter un circuit breaker** → Éviter les cascades d'erreurs
4. **Pré-charger le modèle** → Garantir disponibilité
5. **Ajouter logging détaillé** → Déboguer les problèmes

## Voir `FIX_E3_HTTP500.md` pour les solutions implémentées
