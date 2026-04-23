"""test_pipeline.py — Tests end-to-end du pipeline complet"""

from src.models import CountryTown
from src.e3_slm_fallback import _restore_unit_identifier
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


def test_pipeline_slm_success_recalibrates_confidence(monkeypatch):
    raw = ":59:/123456 MONSIEUR BOURGUIBA HABIB RUE DE LA LIBERTE APPT 4B 8000 NABEUL TUNISIE"

    def fake_apply_slm_fallback(party, model="qwen2.5:0.5b"):
        party.name = ["MONSIEUR BOURGUIBA HABIB"]
        party.address_lines = ["RUE DE LA LIBERTE APPT"]
        party.country_town = CountryTown(country="TN", town="NABEUL", postal_code="8000")
        party.meta.llm_signals = ["slm_applied"]
        party.meta.fallback_used = True
        party.meta.parse_confidence = 0.15
        return party

    monkeypatch.setattr("src.pipeline.needs_slm_fallback", lambda party: True)
    monkeypatch.setattr("src.pipeline.apply_slm_fallback", fake_apply_slm_fallback)

    result, _ = run_pipeline(raw, message_id="TEST_PIPE_SLM_CONF")

    assert result.meta.fallback_used is True
    assert result.country_town.country == "TN"
    assert result.country_town.town == "NABEUL"
    assert result.meta.parse_confidence >= 0.78


def test_restore_unit_identifier_from_raw():
    raw = ":59:/123456 MONSIEUR BOURGUIBA HABIB RUE DE LA LIBERTE APPT 4B 8000 NABEUL TUNISIE"
    assert _restore_unit_identifier("RUE DE LA LIBERTE APPT", raw) == "RUE DE LA LIBERTE APPT 4B"


def test_structured_50f_oued_remel_falls_back_to_city_from_address(monkeypatch):
    monkeypatch.setattr("src.pipeline.needs_slm_fallback", lambda party: False)
    raw = """:50F:/TN5908024011072001462917
1/Mr BEN DJEMAA YASSINE
2/ BP N 4 WED RMAL SFAX
3/TN/OUED REMEL
"""
    result, _ = run_pipeline(raw, message_id="TEST_50F_OUED_REMEL")
    assert result.meta.rejected is False
    assert result.country_town.country == "TN"
    assert result.country_town.town
    assert "REMEL" in result.country_town.town


def test_structured_50f_parses_prefix_postal_town(monkeypatch):
    monkeypatch.setattr("src.pipeline.needs_slm_fallback", lambda party: False)
    raw = """:50F:/FR7630004000380001003225185
1/CLEMENT
2/ZONE INDUSTRIELLE
3/FR/06510 CARROS
2/1ERE AVENUE 7EME RUE
"""
    result, _ = run_pipeline(raw, message_id="TEST_50F_CARROS")
    assert result.meta.rejected is False
    assert result.country_town.country == "FR"
    assert result.country_town.postal_code == "06510"
    assert result.country_town.town == "CARROS"


def test_structured_50f_accepts_st_denis_variant(monkeypatch):
    monkeypatch.setattr("src.pipeline.needs_slm_fallback", lambda party: False)
    raw = """:50F:/FR7630004003160000209278731
1/NOURI SADIK
2/14 AVENUE DU COLONEL FABIEN
3/FR/93200 ST DENIS
"""
    result, _ = run_pipeline(raw, message_id="TEST_50F_ST_DENIS")
    assert result.meta.rejected is False
    assert result.country_town.country == "FR"
    assert result.country_town.postal_code == "93200"
    assert "DENIS" in (result.country_town.town or "")


def test_fragmentation_moves_immeuble_to_building_name(monkeypatch):
    monkeypatch.setattr("src.pipeline.needs_slm_fallback", lambda party: False)
    raw = """:50F:/TN5908500000201053012464
1/SOCIETE DIMA VOYAGES
2/RUE MOHAMED ALI IMMEUBLE
3/TN/SOUSSE
"""
    result, _ = run_pipeline(raw, message_id="TEST_50F_IMMEUBLE")
    best_frag = max(result.fragmented_addresses, key=lambda f: f.fragmentation_confidence)
    assert best_frag.strt_nm == "RUE MOHAMED ALI"
    assert best_frag.bldg_nb is None
    assert best_frag.bldg_nm == "IMMEUBLE"
