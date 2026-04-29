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


def test_pipeline_free_59_keeps_city_from_comma_line(monkeypatch):
    monkeypatch.setattr("src.pipeline.needs_slm_fallback", lambda party: False)
    raw = ":59:Creditor Name\n60 Esplanadi, Helsinki\n"

    result, _ = run_pipeline(raw, message_id="TEST_PIPE_006")

    assert result.meta.rejected is False
    assert result.country_town.country == "FI"
    assert result.country_town.town == "HELSINKI"
    assert result.address_lines == ["60 ESPLANADI"]
    assert result.meta.fallback_used is False


def test_pipeline_50k_resolves_composite_town_for_ghana(monkeypatch):
    monkeypatch.setattr("src.pipeline.needs_slm_fallback", lambda party: False)
    raw = """:50K:/USD1700600011515
MUNIRU HOUSE STYLE ENT
NO. E 59 BUOKROM ESTATE
TAFO, KUMASI
GHANA
"""

    result, _ = run_pipeline(raw, message_id="TEST_PIPE_007")

    assert result.meta.rejected is False
    assert result.country_town.country == "GH"
    assert result.country_town.town == "KUMASI"
    assert result.address_lines == ["NO. E 59 BUOKROM ESTATE"]
    assert not any("requires_manual_verification:town_unverified" in str(w) for w in result.meta.warnings)
    assert result.meta.fallback_used is False


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


def test_pipeline_prefers_city_postcode_fragment_for_town(monkeypatch):
    monkeypatch.setattr("src.pipeline.needs_slm_fallback", lambda party: False)
    raw = """:59:/GB29NWBK60161331926819
ACME Corporation Ltd
45 Canary Wharf
London E14 5AB
United Kingdom
"""
    result, _ = run_pipeline(raw, message_id="TEST_PIPE_GB_LOCALITY")
    assert result.meta.rejected is False
    assert result.country_town.country == "GB"
    assert result.country_town.town == "LONDON"
    assert result.country_town.postal_code == "E14 5AB"


def test_pipeline_does_not_infer_postal_code_from_town_and_country(monkeypatch):
    monkeypatch.setattr("src.pipeline.needs_slm_fallback", lambda party: False)
    raw = """:59:/TN5914700002202576951487
SOCIETE TEST
RUE DE LA REPUBLIQUE
SOUSSE
TUNISIE
"""
    result, _ = run_pipeline(raw, message_id="TEST_PIPE_NO_POSTAL_INFERENCE")

    assert result.country_town.country == "TN"
    assert result.country_town.town == "SOUSSE"
    assert result.country_town.postal_code is None
    assert not any("geo_postal_inferred_from_town_" in str(w) for w in result.meta.warnings)


def test_pipeline_cn_postal_marker_does_not_become_town(monkeypatch):
    monkeypatch.setattr("src.pipeline.needs_slm_fallback", lambda party: False)
    raw = """:50K:/CN12345678901234567890
北京国际贸易有限公司
北京市朝阳区建国门外大街1号
国贸中心A座15层
邮编:100004
"""

    result, _ = run_pipeline(raw, message_id="TEST_PIPE_CN")

    assert result.country_town is not None
    assert result.country_town.country == "CN"
    assert result.country_town.postal_code == "100004"
    assert result.country_town.town is not None
    assert "邮编" not in (result.country_town.town or "")
    assert result.meta.rejected is False


def test_pipeline_keeps_input_town_without_directional_expansion(monkeypatch):
    monkeypatch.setattr("src.pipeline.needs_slm_fallback", lambda party: False)
    raw = """:50F:/TN5908024011072001462917
1/Mr BEN DJEMAA YASSINE
2/ BP N 4 WED RMAL SFAX
3/TN/OUED REMEL
"""

    result, _ = run_pipeline(raw, message_id="TEST_PIPE_TN_OUED_REMEL")

    assert result.country_town is not None
    assert result.country_town.country == "TN"
    assert result.country_town.town == "OUED REMEL"


def test_pipeline_jp_postal_marker_does_not_become_town(monkeypatch):
    monkeypatch.setattr("src.pipeline.needs_slm_fallback", lambda party: False)
    raw = """:50K:/JP12345678901234567890
株式会社サンプル
東京都千代田区
丸の内1-1-1
〒100-0005
"""

    result, _ = run_pipeline(raw, message_id="TEST_PIPE_JP")

    assert result.country_town is not None
    assert result.country_town.country == "JP"
    assert result.country_town.postal_code == "100-0005"
    assert result.country_town.town is not None
    assert "〒" not in (result.country_town.town or "")
    assert result.meta.rejected is False


def test_pipeline_ar_postal_marker_does_not_become_town(monkeypatch):
    monkeypatch.setattr("src.pipeline.needs_slm_fallback", lambda party: False)
    raw = """:50K:/MA12345678901234567890
شركة الاختبار الدولية
الدار البيضاء
الرمز البريدي: 20000
"""

    result, _ = run_pipeline(raw, message_id="TEST_PIPE_AR")

    assert result.country_town is not None
    assert result.country_town.country == "MA"
    assert result.country_town.postal_code == "20000"
    assert result.country_town.town is not None
    assert "الرمز" not in (result.country_town.town or "")
