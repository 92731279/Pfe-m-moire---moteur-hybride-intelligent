from src.e0_preprocess import preprocess
from src.e1_parser import parse_field
from src.e2_validator import validate_party_semantics
from src.e2_address_fragmentation import fragment_party_address


def test_fragmentation_basic():
    raw = """:50K:/FR76123456789012345
DUPONT INDUSTRIES SA
15 RUE DE LA PAIX
75002 PARIS
FRANCE
"""
    e0 = preprocess(raw)
    e1 = parse_field(e0, "MSG_TEST")
    e2 = validate_party_semantics(e1)
    e2 = fragment_party_address(e2)

    assert hasattr(e2, 'fragmented_addresses')
    assert len(e2.fragmented_addresses) >= 1  # type: ignore

    frag = e2.fragmented_addresses[0]  # type: ignore
    assert frag.strt_nm is not None or frag.adr_line  # type: ignore


def test_zone_industrielle_is_not_street():
    from src.pipeline import run_pipeline
    from src.iso20022_mapper import build_iso20022_party_xml_full

    raw = """:50K:/TN4839
2037 ARIANA
Z.I. CHOTRANA 2
SOCIETE MEUBLATEX SA
ATTN DIR FINANCIER
"""
    party, _ = run_pipeline(raw_message=raw, message_id="MSG_TEST_ZI", slm_model="qwen2.5:0.5b")
    xml, payload, errors, semantic = build_iso20022_party_xml_full(party, include_envelope=True)

    pst = payload.get("PstlAdr") or {}
    assert payload.get("Nm") == "SOCIETE MEUBLATEX SA ATTN DIR FINANCIER"
    assert pst.get("StrtNm") is None
    assert pst.get("CtrySubDvsn") == "ZONE INDUSTRIELLE CHOTRANA"
    assert pst.get("BldgNb") == "2"
    assert pst.get("TwnNm") == "ARIANA"
    assert pst.get("Ctry") == "TN"
    assert not semantic.get("errors")
    assert not errors