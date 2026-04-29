import os
from src.e0_preprocess import preprocess
from src.e1_parser import parse_field
from src.pipeline import run_pipeline

raw = """:59:/GB29NWBK60161331926819
ACME Corporation Ltd
45 Canary Wharf
E14 5AB
United Kingdom"""

party, e0 = run_pipeline(raw, "59")
print(party.country_town.model_dump())
