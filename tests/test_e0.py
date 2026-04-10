"""test_e0.py — Tests du prétraitement E0"""

from src.e0_preprocess import preprocess
from src.logger import StepLogger


def test_preprocess_detects_field_type():
    raw = """:50K:/TN5904018104004942712345
BEN ALI AHMED
RUE IBN KHALDOUN
TUNIS"""
    result = preprocess(raw)
    assert result.meta.detected_field_type == "50K"


def test_preprocess_removes_field_prefix():
    raw = """:59:/TN5925048000000102575734
SOCIETE SABRINCO SARL
26 RUE DU TISSAGE ZONE IND.
TNDAOUR HICHER"""
    result = preprocess(raw)
    assert not result.normalized_text.startswith(":59:")
    assert result.lines[0] == "/TN5925048000000102575734"


def test_preprocess_detects_iban_country():
    raw = """:59:/TN5925048000000102575734
SOCIETE SABRINCO SARL"""
    result = preprocess(raw)
    assert result.meta.iban_country == "TN"


def test_preprocess_removes_noise_lines():
    raw = """:50K:
TEL: +216 71 123 456
FAX: +216 71 999 999
BIODATA
GMBH
RUE DE TUNIS
FRANCE"""
    result = preprocess(raw)
    assert "TEL: +216 71 123 456" not in result.lines
    assert "FAX: +216 71 999 999" not in result.lines
    assert len(result.meta.removed_noise_lines) == 2


def test_preprocess_detects_language_french():
    raw = """:50K:
SOCIETE SABRINCO SARL
26 RUE DU TISSAGE ZONE IND.
TUNISIA"""
    result = preprocess(raw)
    assert result.meta.detected_language == "fr"


def test_preprocess_detects_org_entity():
    raw = """:50K:
BIODATA
GMBH
BERLIN
GERMANY"""
    result = preprocess(raw)
    assert result.meta.entity_hint == "OrgId"


def test_preprocess_empty_input():
    result = preprocess("   ")
    assert result.lines == []
    assert "empty_input" in result.meta.warnings


def test_preprocess_logger_collects_logs():
    logger = StepLogger(enabled=False)
    raw = """:50K:
JANE DOE
RUE DE LA REPUBLIQUE
PARIS
FRANCE"""
    _ = preprocess(raw, logger=logger)
    assert len(logger.logs) > 0
    assert any("Début E0 prétraitement" in x for x in logger.logs)
