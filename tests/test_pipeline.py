"""test_pipeline.py — Tests end-to-end du pipeline complet"""

from src.pipeline import run_pipeline


def test_pipeline_clean_50k():
    raw = """:50K:/FR76123456789012345
DUPONT INDUSTRIES SA
15 RUE DE LA PAIX
75002 PARIS
FRANCE
"""
    result, logger = run_pipeline(raw, message_id="TEST_PIPE_001")
    assert result.field_type == "50K"
    assert result.name == ["DUPONT INDUSTRIES SA"]
    assert result.country_town.country == "FR"
    assert result.country_town.town == "PARIS"
    assert result.meta.fallback_used is False
    assert len(logger.events) > 0


def test_pipeline_clean_50f():
    raw = """:50F:/BE30001216371411
1/PHILIPS MARK
2/HOOGSTRAAT 6, APT 6C
3/BE/ANTWERPEN
"""
    result, logger = run_pipeline(raw, message_id="TEST_PIPE_002")
    assert result.field_type == "50F"
    assert result.name == ["PHILIPS MARK"]
    assert result.country_town.country == "BE"


def test_pipeline_returns_logger():
    raw = """:59:/TN5925048000000102575734
SOCIETE SABRINCO SARL
26 RUE DU TISSAGE ZONE IND.
TNDAOUR HICHER
"""
    result, logger = run_pipeline(raw, message_id="TEST_PIPE_003")
    events = logger.as_dicts()
    steps = [e["step"] for e in events]
    assert "E0" in steps
    assert "E1" in steps
    assert "E2" in steps
    assert "OUTPUT" in steps


def test_pipeline_confidence_above_threshold():
    raw = """:50K:/FR76123456789012345
DUPONT INDUSTRIES SA
15 RUE DE LA PAIX
75002 PARIS
FRANCE
"""
    result, _ = run_pipeline(raw, message_id="TEST_PIPE_004")
    assert result.meta.parse_confidence >= 0.7


def test_pipeline_59f_creditor():
    raw = """:59F:/12345678
1/DEPT OF PROMOTION OF SPICY FISH
1/CENTER FOR INTERNATIONALISATION
3/CN
"""
    result, _ = run_pipeline(raw, message_id="TEST_PIPE_005")
    assert result.field_type == "59F"
    assert result.role == "creditor"
    assert result.country_town.country == "CN"
