"""test_e1_free.py — Tests du parsing libre (50K / 59)"""

from src.e0_preprocess import preprocess
from src.e1_parser import parse_field


def test_parse_50k_basic_free():
    raw = """:50K:/FR76123456789012345
DUPONT INDUSTRIES SA
15 RUE DE LA PAIX
75002 PARIS
FRANCE
"""
    p = preprocess(raw)
    result = parse_field(p, message_id="MSG_50K_001")
    assert result.field_type == "50K"
    assert result.role == "debtor"
    assert result.account == "/FR76123456789012345"
    assert result.name == ["DUPONT INDUSTRIES SA"]
    assert "15 RUE DE LA PAIX" in result.address_lines
    assert result.country_town is not None
    assert result.country_town.town == "PARIS"
    assert result.country_town.postal_code == "75002"


def test_parse_59_basic_free():
    raw = """:59:/TN5925048000000102575734
SOCIETE SABRINCO SARL
26 RUE DU TISSAGE ZONE IND.
TN DAOUR HICHER
"""
    p = preprocess(raw)
    result = parse_field(p, message_id="MSG_59_001")
    assert result.field_type == "59"
    assert result.role == "creditor"
    assert result.account == "/TN5925048000000102575734"
    assert result.name == ["SOCIETE SABRINCO SARL"]
    assert result.address_lines == ["26 RUE DU TISSAGE ZONE IND."]
    assert result.country_town is not None
    assert result.country_town.country == "TN"
    assert result.country_town.town == "DAOUR HICHER"


def test_parse_50k_multiline_org_name():
    raw = """:50K:/729615-941
BIODATA
GMBH
BERLIN GERMANY
"""
    p = preprocess(raw)
    result = parse_field(p)
    assert result.name == ["BIODATA GMBH"]
    assert result.country_town is not None
    assert result.country_town.country == "DE"
    assert result.country_town.town == "BERLIN"
    assert "multiline_name_fused:1" in result.meta.warnings


def test_parse_50k_multiline_org_name_agricole():
    raw = """:50K:/TN5908003000515000033732
BANQUE NATIONALE
AGRICOLE
TUNIS TUNISIA
"""
    p = preprocess(raw)
    result = parse_field(p)
    assert result.name == ["BANQUE NATIONALE AGRICOLE"]
    assert result.country_town is not None
    assert result.country_town.country == "TN"
    assert result.country_town.town == "TUNIS"
    assert "multiline_name_fused:1" in result.meta.warnings


def test_parse_50k_inline_name_address():
    raw = """:50K:/FR7630006000011234567890189
JANE DOE RUE DE LA REPUBLIQUE
PARIS FRANCE
"""
    p = preprocess(raw)
    result = parse_field(p)
    assert result.name == ["JANE DOE"]
    assert result.address_lines == ["RUE DE LA REPUBLIQUE"]
    assert result.country_town is not None
    assert result.country_town.town == "PARIS"
    assert "name_address_mixed" in result.meta.warnings


def test_parse_50k_address_not_town_and_capital_fallback():
    raw = """:50K:/729615-941
BIODATA
GMBH
rue de tunis france
"""
    p = preprocess(raw)
    result = parse_field(p)
    assert result.name == ["BIODATA GMBH"]
    assert "rue de tunis" in [x.lower() for x in result.address_lines]
    assert result.country_town is not None
    assert result.country_town.town is None
    assert any(w.startswith("town_reclassified_as_address") for w in result.meta.warnings)


def test_parse_59_detects_org():
    raw = """:59:
COMPAGNIE TUNISIENNE DE NAVIGATION
LOW STREET 7
TUNIS TUNISIA
"""
    p = preprocess(raw)
    result = parse_field(p)
    assert result.is_org is True
    assert result.country_town is not None
    assert result.country_town.country == "TN"
    assert result.country_town.town == "TUNIS"
