# ✅ Fix SLM E3 - Résultats Faux

## 🐛 Bug Identifié

Le SLM retournait les **exemples du prompt** au lieu de traiter les vraies données:

### Cas d'erreur (Ste Automatisme - Tunisie)

**Input:**
```
:59:/TN5903603077019102980938
STE AUTOMATISME INDUSTRIEL
CITE ERRIADH
TUNISIE
```

**Output AVANT (❌ FAUX):**
```json
{
  "name": "LESAFFRE TURQUIE MAYACILIK URETI",  // ❌ C'est un EXEMPLE du prompt!
  "country": "TR",  // ❌ Turquie au lieu de Tunisie
  "town": null
}
```

**Output APRÈS (✅ CORRECT):**
```json
{
  "name": "STE AUTOMATISME INDUSTRIEL",  // ✅ CORRECT
  "country": "TN",  // ✅ Tunisie CORRECT
  "town": "TUNISIE",  // ✅ CORRECT
  "address": ["CITE ERRIADH"]
}
```

---

## 🔍 Cause Racine

**Structure de prompt cassée:**

L'ancien prompt placait les données AVANT les exemples, puis mettait "Maintenant extrais:" SANS relancer les vraies données:

```
MESSAGE:
/TN5903603077019102980938
STE AUTOMATISME INDUSTRIEL
...

EXEMPLES:

Input: "JANE DOE..."
...

Input: "LESAFFRE TURQUIE MAYACILIK URETI\nTURQUIE"  ← Dernier exemple
name: LESAFFRE TURQUIE MAYACILIK URETI
country: TR

Maintenant extrais:  ← Pas de données après!
```

Le petit SLM (qwen2.5:0.5b) s'y perd et retourne l'exemple à la place.

---

## ✅ Solution Appliquée

**Restructurer le prompt pour:**
1. Mettre EXEMPLES D'ABORD (courts et clairs)
2. Ajouter délimiteur visible `---`
3. Puis ajouter les **VRAIES DONNÉES EXPLICITEMENT**
4. Finir par `Output:` (consigne claire de générer)

**Nouveau format:**

```
TÂCHE: Extraire...
RÈGLES:
...
EXEMPLES:
Input: "JANE DOE\nRUE..."
Output:
name: JANE DOE
...

Input: "MOHSEN..."
Output:
...

---

À TRAITER (même format, répondre UNIQUEMENT le Output):

Input: "/TN5903603077019102980938\nSTE AUTOMATISME INDUSTRIEL\nCITE ERRIADH\nTUNISIE"
Output:  ← SLM génère ici
```

---

## 📝 Fichier Modifié

**[src/e3_slm_fallback.py](src/e3_slm_fallback.py#L367)** - Fonction `_build_structured_prompt()` (lignes 367-430)

### Changements clés:

| Avant | Après |
|-------|-------|
| Données + Exemples mélangés | ✅ Exemples → Données (séquence claire) |
| 4 exemples longs | ✅ 2 exemples courts |
| "Maintenant extrais:" sans contexte | ✅ "À TRAITER..." + "Output:" explicite |
| Format loose | ✅ Format strict avec `---` séparateur |

---

## 🧪 Validation du Fix

### Test du prompt remanié:

```bash
source .venv/bin/activate
python3 test_slm_fix.py
```

**Résultats du test:**
```
✅ Nom CORRECT: STE AUTOMATISME INDUSTRIEL
✅ Pays CORRECT: TN (Tunisie)
✅ Ville OK
```

---

## 🚀 Prochaines Actions

### 1. Redémarrer l'application
```bash
streamlit run app/streamlit_app2.py
```

### 2. Re-tester le message Ste Automatisme
Le résultat JSON devrait maintenant afficher:
- `name: ["STE AUTOMATISME INDUSTRIEL"]` ✅
- `country: "TN"` ✅ (Tunisie, pas Turquie)
- `town: "TUNISIE"` ✅

### 3. Tester d'autres cas
Vérifier avec d'autres messages MT103 que les résultats sont cohérents.

---

## 📊 Comparaison Avant/Après

| Métrique | Avant | Après |
|----------|-------|-------|
| **Retour exemple du prompt** | ❌ Oui (bug) | ✅ Non |
| **Nom extrait correctement** | ❌ Non | ✅ Oui |
| **Pays détecté correctement** | ❌ Non | ✅ Oui |
| **Addresses fragmentées** | ❌ Mauvais | ✅ Correct |
| **Confiance de résultat** | ❌ Faible (40%) | ✅ Plus haute |

---

## 💡 Insights Techniques

### Pourquoi c'était broken:

1. **Small LLM confusion**: qwen2.5:0.5b est petit (397 MB) et peut se perdre avec une structure de prompt confuse
2. **Exemple "Turquie"**: Le dernier exemple contenait "TR" (Turquie) qui collait directement avant "Maintenant extrais:"
3. **Manque de délimiteur**: Pas de séparation claire entre exemples et données réelles

### Pourquoi ça marche maintenant:

1. ✅ Structure super claire avec `---` séparateur
2. ✅ Input/Output répétée pour les vraies données  
3. ✅ Instructions explicites "À TRAITER... répondre UNIQUEMENT le Output"
4. ✅ Moins d'exemples (2 au lieu de 4) = moins de bruit

---

## 🔗 Références

- **Bug report**: Résultats faux pour "Ste Automatisme Industriel - Tunis"
- **Root cause**: Structure du prompt E3 confuse pour petit SLM
- **Fix**: Refactoriser prompt avec délimiteurs clairs et données explicites
- **Status**: ✅ VALIDÉ via test_slm_fix.py

---

## ⚠️ Notes Importantes

1. **Cache SLM**: Il y a un cache dans E3. Les anciennes entrées peuvent rester en cache.
   - Solution: Redémarrer l'app pour vider le cache
   
2. **Model parameter**: Le fix fonctionne avec `qwen2.5:0.5b`
   - Si vous changez de modèle (ex: phi3:mini), testez à nouveau
   
3. **Prompt structure**: Les instructions sont maintenants en français/anglais simple
   - Évite la confusion pour le SLM

---

## ✅ Checklist de validation

- [x] Prompt remanié et testée
- [x] Test automatisé `test_slm_fix.py` ✓
- [x] Résultats corrects pour cas d'erreur
- [x] Syntaxe Python validée
- [ ] Test manuel via UI Streamlit
- [ ] Tester avec d'autres cas de test
- [ ] Documenter dans README si besoin

