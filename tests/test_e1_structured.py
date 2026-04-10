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
    assert result.dob == "19720830"
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


def test_parse_50f_line_8_is_kept():
    raw = """:50F:CUST/DE/ABC BANK/123456
1/MANN GEORG
2/LOW STREET 7
3/DE/FRANKFURT
8/7890
"""
    p = preprocess(raw)
    result = parse_field(p)
    assert result.postal_complement == "7890"


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
