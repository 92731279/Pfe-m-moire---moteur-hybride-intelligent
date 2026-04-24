"""test_e3.py — Tests du fallback SLM (déclenchement uniquement)"""

from src.e0_preprocess import preprocess
from src.e1_parser import parse_field
from src.e2_validator import validate_party_semantics
from src.e3_slm_fallback import E3SLMFallback, needs_slm_fallback
from src.models import CanonicalMeta, CanonicalParty, CountryTown


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


def test_apply_slm_result_does_not_override_reliable_structured_country():
    fallback = E3SLMFallback()
    party = CanonicalParty(
        message_id="MSG_SLM_004",
        field_type="50F",
        role="debtor",
        account="/US9876543210",
        name=["SMITH JOHN ROBERT"],
        address_lines=["789 MARKET STREET, APT 12B"],
        country_town=CountryTown(country="US", town="SAN FRANCISCO", postal_code="94103"),
        is_org=False,
        meta=CanonicalMeta(source_format="50F", parse_confidence=0.6, warnings=[]),
    )

    slm_result = {
        "name": "JOHN ROBERT SMITH",
        "address_lines": ["MARKET STREET, APT 12B"],
        "town": "US SAN FRANCISCO",
        "country": "CA",
        "postal_code": "94103",
    }

    updated = fallback._apply_slm_result(party, slm_result)
    assert updated.country_town is not None
    assert updated.country_town.country == "US"
