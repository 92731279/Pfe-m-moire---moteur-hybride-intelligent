from src.pipeline import run_pipeline

tests = {
    "MSG_NEWYORK": """:59:/US1234
JOHN SMITH
123 MAIN ST
NEW YORK""",
    "MSG_TUNIS_BELVEDERE": """:59:/TN1234
ETABL STABLE TEMENOS FRANCE
RUE LAC LOCHNESS ZONE
TUNIS BELVEDERE""",
    "MSG_SABRINCO": """:59:/TN5925048000000102575734
SOCIETE SABRINCO SARL
ZONE IND
TNDAOUR HICHER"""
}

for msg_id, content in tests.items():
    print(f"\\n--- Processing {msg_id} ---")
    res, _ = run_pipeline(content, message_id=msg_id)
    print(f"Confidence: {res.meta.parse_confidence}")
    print(f"Name: {res.name[0] if res.name else ''}")
    print(f"Country: {res.country_town.country if res.country_town else None}")
    print(f"Town: {res.country_town.town if res.country_town else None}")
    print(f"Warnings: {res.meta.warnings}")
