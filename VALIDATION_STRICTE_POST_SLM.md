# 🔧 RÉSOLUTION: Validation Stricte Post-SLM et Post-Inférence Postale

## Problème Identifié
Le moteur SWIFT acceptait et affichait des résultats faux basés sur:
1. **Résultats SLM non validés**: SLM retourne une ville, moteur l'accepte sans vérifier en GeoNames
2. **Inférences postales non fiables**: Code postal invalide → SLM infère une ville → moteur l'accepte

### Exemple du bug initial
```
Input:  :50K:/123456789
        JOHN DOE CO
        10 MAIN ST
        NEWYORK US

Output: Ville: NEVES (inféré du code postal "10 MAIN" pour pays ST)
        Decision: ✅ MESSAGE ACCEPTÉ
        
Problem: "10 MAIN" n'est PAS un code postal valide pour ST
         SLM infère "NEVES" (vraie ville de ST) MAIS sans base solide
         Moteur accepte comme "correct" → Dangereux!
```

---

## Solutions Implémentées

### 1. **Validation Stricte POST-SLM** (`src/e3_slm_fallback.py`)
✅ **Avant**: Résultats SLM acceptés sans validation
```python
# ANCIEN (dangéreux)
if slm_result.get('town'):
    party.country_town.town = slm_town  # Applique directement ❌
    updated = True
```

✅ **Après**: Validation GeoNames obligatoire
```python
# NOUVEAU (sûr)
if slm_result.get('town'):
    validated_town, reason = validate_slm_town(country, slm_town, postal)
    
    if not validated_town and town_was_unconfirmed:
        # 🚫 REJETER - marquer pour révision manuelle
        warnings.append('slm_validation_failed_strict')
        meta.requires_manual_review = True
        slm_result['town'] = None  # NE PAS appliquer
    elif validated_town:
        # ✅ APPLIQUER - validation réussie
        party.country_town.town = validated_town
        updated = True
```

**Logique clé**:
- SLM n'est appelé que si la ville est MANQUANTE ou INCERTAINE
- Si SLM retourne un résultat → VALIDER strictement en GeoNames
- Si validation échoue → REJETER et marquer pour révision manuelle
- Si validation réussit → APPLIQUER

### 2. **Validation Stricte POST-Inférence Postale** (`src/pipeline.py`)
✅ **Avant**: Inférences postales acceptées directement
```python
# ANCIEN (problématique)
inferred_town = infer_city_from_postal_code(country, postal)
if inferred_town:
    party.country_town.town = inferred_town  # Applique sans vérifier ❌
```

✅ **Après**: Validation GeoNames de l'inférence
```python
# NOUVEAU (sûr)
inferred_town = infer_city_from_postal_code(country, postal)

if inferred_town:
    # VALIDER l'inférence
    validated_place = find_place(country, inferred_town)
    
    if not validated_place:
        # 🚫 Inférence REJETÉE
        warnings.append(f'postal_inference_rejected:{inferred_town}:not_in_geonames')
        inferred_town = None
    else:
        # ✅ Inférence VALIDÉE
        party.country_town.town = inferred_town
```

### 3. **Politiques de Rejet Strictes** (`src/rejection_policy.py`)
✅ **NOUVEAU**: Rejet automatique si validation SLM échoue
```python
# NIVEAU 0: Validation SLM stricte (priorité absolue)
if any("slm_validation_failed_strict" in str(w) for w in warnings):
    reasons.append("slm_validation_failed:fallback_results_unverified")
    # ➜ MESSAGE REJETÉ
```

---

## Résultats des Tests

### Test 1: Invalid postal for ST
```
Input:  :50K:/123456789
        JOHN DOE CO
        10 MAIN ST
        (no city, invalid postal for ST)

Processing:
1. E1: Parses account, name, city?, postal
2. E2: City manquante, SLM appelé
3. E3: SLM infère "SÃO TOMÉ" du postal "10 MAIN"
4. ✅ VALIDATION POST-SLM: "SÃO TOMÉ" NOT found in GeoNames for ST
5. ❌ REJECT: slm_validation_failed_strict added
6. Result: REJECTED (proper) ✅

Ancien comportement: ACCEPTÉ comme "NEVES" ❌
Nouveau comportement: REJETÉ ✅
```

### Test 2: New postal inference validation
```
Input:  Code postal invalide pour ST
Output: "SÃO TOMÉ" inféré par SLM
        
Processing:
1. postal_inference_slm_ST:10 MAIN→SÃO TOMÉ
2. find_place("ST", "SÃO TOMÉ") → NULL (pas en GeoNames for ST)
3. ❌ postal_inference_rejected:SÃO TOMÉ:not_in_geonames
4. Inférence NOT appliquée

Ancien comportement: ACCEPTÉ ❌
Nouveau comportement: REJETÉ ✅
```

---

## Garanties Désormais Appliquées

| Situation | Ancien | Nouveau |
|-----------|--------|---------|
| SLM retourne ville → GeoNames confirme | ✅ Accepté | ✅ Accepté |
| SLM retourne ville → GeoNames rejette | ✅ Accepté ❌ | ❌ REJETÉ ✅ |
| Postal infère ville → GeoNames confirme | ✅ Accepté | ✅ Accepté |
| Postal infère ville → GeoNames rejette | ✅ Accepté ❌ | ❌ REJETÉ ✅ |
| Résultat faux mais confiance élevée | ✅ Accepté ❌ | ❌ REJETÉ ✅ |

---

## Code Changes Summary

### Files Modified:
1. **src/e3_slm_fallback.py**
   - Ligne ~650-680: Validation stricte des résultats SLM
   - Ligne ~715-730: Pénalité de confiance si SLM échoue
   - Logic: SLM results only applied if GeoNames validated

2. **src/pipeline.py**
   - Ligne ~241-310: Validation stricte des inférences postales
   - Ajout: `validated_place = find_place(country, inferred_town)`
   - Logic: Postal inferences only applied if GeoNames confirmed

3. **src/rejection_policy.py**
   - Ligne ~20-30: NOUVEAU "slm_validation_failed_strict" check
   - Priority: Stricte validation failure = AUTO REJECT

### Nouvelles Flags/Warnings:
- `slm_validation_failed_strict`: SLM result failed GeoNames validation
- `postal_inference_rejected:{town}:not_in_geonames`: Postal inference not found
- `requires_manual_review=True`: Manual human review required

---

## Conclusion

**Avant**: Moteur acceptait n'importe quoi tant que SLM/inférence retournait quelque chose
**Après**: ✅ Stricte validation ALL fallback results contre GeoNames AVANT acceptance

```
USER INPUT → E0→E1→E2→E2.5→E3(SLM)→[✅ VALIDER EN GEONAMES]→Acceptance Decision
                                        ↑
                                   New Gate!
```

Le moteur refuse maintenant les résultats "plausibles mais non vérifiés".
