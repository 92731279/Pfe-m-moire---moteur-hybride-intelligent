import os
from src.e0_preprocess import preprocess
from src.e1_parser import parse_field

raw = """:59:/GB29NWBK60161331926819
ACME Corporation Ltd
45 Canary Wharf
E14 5AB
United Kingdom"""

e0 = preprocess(raw)
e1 = parse_field(e0, "59")
print(e1.country_town.model_dump())
