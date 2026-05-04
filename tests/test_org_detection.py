from src.e1_parser import _detect_org


def test_org_hint_inside_person_name_does_not_mark_organisation():
    assert _detect_org(["MARIEM HATTAB"]) is False


def test_org_hint_as_standalone_suffix_marks_organisation():
    assert _detect_org(["ACME AB"]) is True
    assert _detect_org(["SOCIETE MEUBLATEX SA"]) is True
