import os
from src.e0_preprocess import preprocess
from src.e1_parser import parse_field
from src.e2_validator import validate_party_semantics
from src.e3_slm_fallback import apply_slm_fallback
from src.pipeline import run_pipeline

raw = """:59:/GB29NWBK60161331926819
ACME Corporation Ltd
45 Canary Wharf
E14 5AB
United Kingdom"""

e0 = preprocess(raw)
e1 = parse_field(e0, "59")
e2 = validate_party_semantics(e1)
e3 = apply_slm_fallback(e2, "qwen2.5:0.5b")
print("E3 output:", getattr(e3, "meta", {}).llm_signals if hasattr(e3, "meta") else "none")
print("E3 town:", getattr(e3.country_town, "town", "None"))
print("E3 raw:", e3)
