from src.e0_preprocess import preprocess
from src.e1_parser import parse_field
from src.e2_validator import validate_party_semantics
raw = """:50K:/729615-941
BIODATA
GMBH
MARSEILLE GERMANY
"""
p = preprocess(raw)
result = parse_field(p, message_id="MSG_E2_002")
result = validate_party_semantics(result)
print(result.meta.warnings)
