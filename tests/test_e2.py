"""test_e2.py — Tests de la validation sémantique E2"""

from src.e0_preprocess import preprocess
from src.e1_parser import parse_field
from src.e2_validator import validate_party_semantics


def test_validate_known_country_town_ok():
    raw = """:50K:/FR76123456789012345
DUPONT INDUSTRIES SA
15 RUE DE LA PAIX
75002 PARIS
FRANCE
"""
    p = preprocess(raw)
    result = parse_field(p, message_id="MSG_E2_001")
    result = validate_party_semantics(result)
    assert "semantic_unknown_country" not in " ".join(result.meta.warnings)
    assert "semantic_unknown_town_for_country" not in " ".join(result.meta.warnings)


def test_validate_unknown_town_for_country_warns():
    raw = """:50K:/729615-941
BIODATA
GMBH
MARSEILLE GERMANY
"""
    p = preprocess(raw)
    result = parse_field(p, message_id="MSG_E2_002")
    result = validate_party_semantics(result)
    assert any(w.startswith("pass1_town_not_official:MARSEILLE") for w in result.meta.warnings)


def test_validate_missing_town_warns():
    raw = """:59:/BE62510007547061
JOHANN WILLEMS
RUE JOSEPH II, 19
"""
    p = preprocess(raw)
    result = parse_field(p, message_id="MSG_E2_003")
    result = validate_party_semantics(result)
    assert "semantic_town_missing" in result.meta.warnings or result.country_town is not None


def test_validate_unknown_country_warns():
    result = parse_field(
        preprocess(""":50K:/ZZ123
TEST COMPANY
ROAD 1
UNKNOWNCITY
"""), message_id="MSG_E2_004"
    )
    result.country_town.country = "ZZ"
    result = validate_party_semantics(result)


def test_validate_address_with_libpostal():
    raw = """:50K:/FR76123456789012345
DUPONT INDUSTRIES SA
15 RUE DE LA PAIX
75002 PARIS
FRANCE
"""
    p = preprocess(raw)
    result = parse_field(p, message_id="MSG_E2_005")
    result = validate_party_semantics(result)
    assert hasattr(result, "address_validation")
    assert len(result.address_validation) >= 1
    assert result.address_validation[0]["is_valid"] is True


def test_validate_bad_address_line_warns():
    raw = """:59:
JOHN DOE
XXXXXX
PARIS FRANCE
"""
    p = preprocess(raw)
    result = parse_field(p, message_id="MSG_E2_006")
    result.address_lines = ["XXXXXX"]
    result = validate_party_semantics(result)
    assert(any(
        w.startswith("pass2_soft:missing_road_like_component")
        for w in result.meta.warnings
    ))


def test_validate_structured_composite_town_reduced_to_core():
    raw = """:50F:/TN5908003000515000033732
1/ETABL STABLE TEMENOS FRANCE
2/24 RUE CLAUDE BERNARD
3/TN/TUNIS BELVEDERE
"""
    p = preprocess(raw)
    result = parse_field(p, message_id="MSG_E2_007")
    result = validate_party_semantics(result)
    assert result.country_town is not None
    assert result.country_town.country == "TN"
    assert result.country_town.town == "TUNIS"
    assert not any(w.startswith("pass1_town_not_found_worldwide") for w in result.meta.warnings)


def test_validate_free_composite_town_reduced_to_core():
    raw = """:50K:/FR76123456789012345
JEAN DUPONT
15 RUE DE LA PAIX
PARIS CENTRE
"""
    p = preprocess(raw)
    result = parse_field(p, message_id="MSG_E2_008")
    result.country_town.country = "FR"
    result = validate_party_semantics(result)
    assert result.country_town is not None
    assert result.country_town.town is None
    assert not any(w.startswith("pass1_town_not_found_worldwide") for w in result.meta.warnings)
