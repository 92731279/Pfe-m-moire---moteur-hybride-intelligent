"""test_e1_structured.py — Tests du parsing structuré (50F / 59F)"""

from src.e0_preprocess import preprocess
from src.e1_parser import parse_field


def test_parse_50f_basic():
    raw = """:50F:/BE30001216371411
1/PHILIPS MARK
2/HOOGSTRAAT 6, APT 6C
3/BE/ANTWERPEN
"""
    p = preprocess(raw)
    result = parse_field(p, message_id="MSG_001")
    assert result.field_type == "50F"
    assert result.role == "debtor"
    assert result.account == "/BE30001216371411"
    assert result.name == ["PHILIPS MARK"]
    assert result.address_lines == ["HOOGSTRAAT 6, APT 6C"]
    assert result.country_town is not None
    assert result.country_town.country == "BE"
    assert result.country_town.town == "ANTWERPEN"


def test_parse_50f_with_dob_and_pob():
    raw = """:50F:/BE30001216371411
1/PHILIPS MARK
3/BE/ANTWERPEN
4/19720830
5/BE/BRUSSELS
    """
    p = preprocess(raw)
    result = parse_field(p)
    assert result.dob is not None
    assert result.dob.raw == "19720830"
    assert result.dob.year == "1972"
    assert result.dob.month == "08"
    assert result.dob.day == "30"
    assert result.pob is not None
    assert result.pob.country == "BE"
    assert result.pob.city == "BRUSSELS"
    assert "4_and_5_must_appear_together" not in result.meta.warnings


def test_parse_50f_warns_if_4_without_5():
    raw = """:50F:/BE30001216371411
1/PHILIPS MARK
3/BE/ANTWERPEN
4/19720830
"""
    p = preprocess(raw)
    result = parse_field(p)
    assert "4_and_5_must_appear_together" in result.meta.warnings


def test_parse_50f_party_identifier():
    raw = """:50F:NIDN/DE/121231234342
1/MANN GEORG
3/DE/FRANKFURT
"""
    p = preprocess(raw)
    result = parse_field(p)
    assert result.party_id is not None
    assert result.party_id.code == "NIDN"
    assert result.party_id.country == "DE"
    assert result.party_id.identifier == "121231234342"


def test_parse_50f_national_id():
    raw = """:50F:/TN5908003000716021093649
1/NGUYEN VAN AN
3/TN/TUNIS
7/TN/123456789
"""
    p = preprocess(raw)
    result = parse_field(p)
    assert result.national_id == "123456789"


def test_parse_50f_line_8_extends_party_identifier():
    raw = """:50F:CUST/DE/ABC BANK/123456
1/MANN GEORG
2/LOW STREET 7
3/DE/FRANKFURT
8/Issue-2024
"""
    p = preprocess(raw)
    result = parse_field(p)
    assert result.party_id is not None
    assert result.party_id.identifier == "123456Issue-2024"
    assert result.postal_complement is None
    assert "T56_invalid_8_continuation" not in result.meta.warnings


def test_parse_50f_line_8_extends_national_id():
    raw = """:50F:/TN5908003000716021093649
1/NGUYEN VAN AN
3/TN/TUNIS
7/TN/123456789
8/890
"""
    p = preprocess(raw)
    result = parse_field(p)
    assert result.national_id == "123456789890"


def test_parse_50f_line_8_narrative_is_not_appended_to_passport_id():
    raw = """:50F:CCPT/FR/AB1234567
1/DUPONT MARIE CLAIRE
2/25 AVENUE DES CHAMPS-ELYSEES
3/FR/PARIS
8/Passport issued 2020
"""
    p = preprocess(raw)
    result = parse_field(p)

    assert result.party_id is not None
    assert result.party_id.identifier == "AB1234567"
    assert "line_8_non_identifier_narrative" in result.meta.warnings
    assert "T56_invalid_8_semantic_content" in result.meta.warnings


def test_parse_50f_structured_us_city_state_zip_extracts_city_and_postal():
    raw = """:50F:/US9876543210
1/SMITH JOHN ROBERT
2/789 MARKET STREET, APT 12B
3/US/SAN FRANCISCO, CA 94103
4/19850615
5/US/CHICAGO
6/US/BANK OF AMERICA/987654321
"""
    p = preprocess(raw)
    result = parse_field(p)

    assert result.country_town is not None
    assert result.country_town.country == "US"
    assert result.country_town.town == "SAN FRANCISCO"
    assert result.country_town.postal_code == "94103"


def test_parse_59f_line_8_without_parent_warns():
    raw = """:59F:/12345678
1/JOHN SIMONS
3/GB/LONDON
8/BP 120
"""
    p = preprocess(raw)
    result = parse_field(p)
    assert "orphan_continuation_line" in result.meta.warnings
    assert "T56_invalid_8_continuation" in result.meta.warnings


def test_parse_59f_basic():
    raw = """:59F:/12345678
1/DEPT OF PROMOTION OF SPICY FISH
1/CENTER FOR INTERNATIONALISATION
3/CN
"""
    p = preprocess(raw)
    result = parse_field(p, message_id="MSG_059F")
    assert result.field_type == "59F"
    assert result.role == "creditor"
    assert result.account == "/12345678"
    assert result.name == ["DEPT OF PROMOTION OF SPICY FISH", "CENTER FOR INTERNATIONALISATION"]
    assert result.country_town is not None
    assert result.country_town.country == "CN"


def test_parse_59f_missing_3_warns():
    raw = """:59F:/12345678
1/JOHN SIMONS
2/3658 WITMER ROAD
"""
    p = preprocess(raw)
    result = parse_field(p)
    assert "missing_mandatory_3" in result.meta.warnings
    assert result.meta.parse_confidence < 1.0
