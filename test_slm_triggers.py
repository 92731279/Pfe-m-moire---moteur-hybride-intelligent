"""test_slm_triggers.py — Exemples qui déclenchent le SLM fallback (E3)"""

import sys
sys.path.insert(0, '.')

from src.e0_preprocess import preprocess
from src.e1_parser import parse_field
from src.e2_validator import validate_party_semantics
from src.e3_slm_fallback import needs_slm_fallback

def test_slm(name, raw_message):
    """Teste si un message déclenche le SLM"""
    try:
        p = preprocess(raw_message)
        r = parse_field(p)
        r = validate_party_semantics(r)
        
        use_slm = needs_slm_fallback(r)
        
        print(f"\n{'='*60}")
        print(f"📌 {name}")
        print(f"{'='*60}")
        print(f"Confiance      : {r.meta.parse_confidence}")
        print(f"Warnings       : {r.meta.warnings}")
        print(f"SLM trigger    : {'🔴 YES (SLM activé)' if use_slm else '🟢 NO'}")
        print(f"Name           : {r.name}")
        print(f"Address        : {r.address_lines}")
        print(f"Town/Country   : {r.country_town}")
        
    except Exception as e:
        print(f"\n❌ Erreur: {e}")

# ============================================================================
# CAS 1 : Confiance très basse (< 0.70) → SLM TOUJOURS activé
# ============================================================================

print("\n" + "="*60)
print("CAS 1 : CONFIANCE TRÈS BASSE (< 0.70)")
print("="*60)

test_slm(
    "Cas 1a : Message mal structuré",
    """
:50K:/DE123456789
UNKNOWN CITY NAME
NO COUNTRY
"""
)

test_slm(
    "Cas 1b : Données incohérentes",
    """
:50K:/XX999999999
???
###
"""
)

# ============================================================================
# CAS 2 : Nom et adresse mélangés (name_address_mixed)
# ============================================================================

print("\n" + "="*60)
print("CAS 2 : NOM ET ADRESSE MÉLANGÉS")
print("="*60)

test_slm(
    "Cas 2 : Ambiguïté nom/adresse",
    """
:50K:/FR76123456789
JEAN DUPONT 42 RUE DU FAUBOURG
PARIS FRANCE
"""
)

# ============================================================================
# CAS 3 : Ville classée comme adresse (town_reclassified_as_address)
# ============================================================================

print("\n" + "="*60)
print("CAS 3 : VILLE CLASSÉE COMME ADRESSE")
print("="*60)

test_slm(
    "Cas 3 : Ambiguïté adresse/ville",
    """
:50K:/FR76123456789
PARIS
RUE DE LA PAX
FRANCE
"""
)

# ============================================================================
# CAS 4 : Ville inconnue pour le pays (semantic_unknown_town_for_country)
# ============================================================================

print("\n" + "="*60)
print("CAS 4 : VILLE INCONNUE POUR LE PAYS")
print("="*60)

test_slm(
    "Cas 4 : Ville inexistante",
    """
:50K:/FR76123456789
DUPONT SARL
12 RUE PRINCIPALE
XENOPOLIS FRANCE
"""
)

# ============================================================================
# CAS 5 : Pas d'adresse valide (semantic_no_valid_address_detected)
# ============================================================================

print("\n" + "="*60)
print("CAS 5 : PAS D'ADRESSE VALIDE DÉTECTÉE")
print("="*60)

test_slm(
    "Cas 5 : Adresse vide/invalide",
    """
:50K:/FR76123456789
SOCIETE TEST
???
PARIS FRANCE
"""
)

# ============================================================================
# CAS 6 : Ambiguïté pays/ville en fin de message (ambiguous_city_country_tail)
# ============================================================================

print("\n" + "="*60)
print("CAS 6 : AMBIGUÏTÉ PAYS/VILLE EN FIN")
print("="*60)

test_slm(
    "Cas 6 : Pays/ville ambigu",
    """
:50K:/FR76123456789
DUPONT SA
25 AVENUE PRINCIPALE
FRANCE GERMANY
"""
)

# ============================================================================
# CAS 7 : Confiance basse + multi-line name fused
# ============================================================================

print("\n" + "="*60)
print("CAS 7 : NOM SUR PLUSIEURS LIGNES + CONFIANCE BASSE")
print("="*60)

test_slm(
    "Cas 7 : Nom fragmenté",
    """
:50K:/FR76123456789
Jean
PAUL
DUBOIS
PARIS
"""
)
