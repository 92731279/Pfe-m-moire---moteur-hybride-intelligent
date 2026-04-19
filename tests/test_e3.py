"""test_e3.py — Tests du fallback SLM (déclenchement uniquement)"""

from src.e0_preprocess import preprocess
from src.e1_parser import parse_field
from src.e2_validator import validate_party_semantics
from src.e3_slm_fallback import needs_slm_fallback


def test_slm_trigger_on_name_address_mixed():
    raw = """:50K:/FR7630006000011234567890189
JANE DOE RUE DE LA REPUBLIQUE
PARIS FRANCE
"""
    p = preprocess(raw)
    r = parse_field(p, message_id="MSG_SLM_001")
    r = validate_party_semantics(r)


def test_slm_trigger_on_multiline_name():
    raw = """:50K:/729615-941
BIODATA
GMBH
BERLIN GERMANY
"""
    p = preprocess(raw)
    r = parse_field(p, message_id="MSG_SLM_002")
    r = validate_party_semantics(r)


def test_slm_not_triggered_on_clean_case():
    raw = """:50K:/FR76123456789012345
DUPONT INDUSTRIES SA
15 RUE DE LA PAIX
75002 PARIS
FRANCE
"""
    p = preprocess(raw)
    r = parse_field(p, message_id="MSG_SLM_003")
    r = validate_party_semantics(r)
