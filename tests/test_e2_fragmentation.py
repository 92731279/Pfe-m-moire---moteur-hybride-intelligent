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