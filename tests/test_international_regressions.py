from src.e1_parser import _detect_org
from src.pipeline import run_pipeline


def test_postal_country_line_does_not_treat_country_as_town():
    raw = """:59:/DE89370400440532013000
KARIM BEN SALEM
KAISERSTRASSE 21
60311 DE"""

    result, _ = run_pipeline(raw, message_id="REG_DE_POSTAL_COUNTRY", disable_slm=True)

    assert result.country_town.country == "DE"
    assert result.country_town.postal_code == "60311"
    assert result.country_town.town != "FEDERAL REPUBLIC OF GERMANY"
    assert result.country_town.town != "DE"


def test_netherlands_alphanumeric_postal_code_is_preserved():
    raw = """:59:/NL91ABNA0417164300
ANNA BERG
DAMRAK 45
1012 LP AMSTERDAM NL"""

    result, _ = run_pipeline(raw, message_id="REG_NL_POSTAL", disable_slm=True)

    assert result.country_town.country == "NL"
    assert result.country_town.postal_code == "1012 LP"
    assert result.country_town.town == "AMSTERDAM"


def test_resolved_composite_town_does_not_need_slm():
    raw = """:59:/DE44500105175407324931
GLOBAL PARTS GMBH
INDUSTRIESTRASSE 7
70565 STUTTGART DE"""

    result, _ = run_pipeline(raw, message_id="REG_DE_COMPOSITE", disable_slm=True)

    assert result.country_town.country == "DE"
    assert result.country_town.postal_code == "70565"
    assert result.country_town.town == "STUTTGART"
    assert not any(str(w).startswith("pass1_town_not_official:") for w in result.meta.warnings)


def test_three_word_person_name_defaults_to_private_person():
    assert _detect_org(["OMAR EL HADDAD"]) is False
