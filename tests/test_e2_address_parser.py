"""test_e2_address_parser.py — Tests du parser d'adresse libpostal"""

from src.e2_address_parser import parse_address_line


def test_parse_simple_french_address():
    result = parse_address_line("15 RUE DE LA PAIX PARIS")
    assert result["is_valid"] is True
    assert isinstance(result["components"], dict)
    assert len(result["parsed"]) > 0


def test_parse_address_with_unit():
    result = parse_address_line("HOOGSTRAAT 6, APT 6C")
    assert result["is_valid"] is True
    assert len(result["parsed"]) > 0


def test_parse_address_with_building():
    result = parse_address_line("RUE IBN KHALDOUN, IMM COLISEE")
    assert result["is_valid"] is True
    assert len(result["parsed"]) > 0


def test_empty_address():
    result = parse_address_line("")
    assert result["is_valid"] is False
    assert "empty_address_line" in result["warnings"]
