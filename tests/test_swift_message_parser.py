from src.swift_message_parser import extract_party_fields, extract_swift_fields


FULL_MESSAGE = """\x01{1:F01BIATTNTTXXXX4333652311}{2:I202COBADEFFXXXXN}{4:
:20:FT24200431063957
:32A:240724EUR722,00
:50F:/TN5908003000515000002789
1/SABRINA CONFECTION
2/ZONE INDUSTRIELLE KSAR SAID
3/TN/MANOUBA
:59F:/TN5925048000000102575734
1/FLEN BEN FLEN
2/TUNIS
3/TN/TN 8090
:70:TEST
-}\x03"""


def test_extract_swift_fields_from_full_fin_message():
    fields = extract_swift_fields(FULL_MESSAGE)

    assert [field["tag"] for field in fields] == ["20", "32A", "50F", "59F", "70"]
    assert fields[2]["lines"] == [
        "/TN5908003000515000002789",
        "1/SABRINA CONFECTION",
        "2/ZONE INDUSTRIELLE KSAR SAID",
        "3/TN/MANOUBA",
    ]


def test_extract_party_fields_rebuilds_engine_inputs():
    parties = extract_party_fields(FULL_MESSAGE)

    assert [party["tag"] for party in parties] == ["50F", "59F"]
    assert [party["role"] for party in parties] == ["debtor", "creditor"]
    assert parties[0]["raw_party_field"] == (
        ":50F:\n"
        "/TN5908003000515000002789\n"
        "1/SABRINA CONFECTION\n"
        "2/ZONE INDUSTRIELLE KSAR SAID\n"
        "3/TN/MANOUBA"
    )
