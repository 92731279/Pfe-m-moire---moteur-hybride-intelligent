from src.iso20022_mapper import (
    build_iso20022_party_payload,
    build_iso20022_party_xml,
    validate_iso20022_party_payload,
)
from src.models import (
    CanonicalMeta,
    CanonicalParty,
    CountryTown,
    DateOfBirth,
    FragmentedAddress,
    PartyIdentifier,
    PlaceOfBirth,
)


def test_build_iso20022_payload_for_private_party():
    party = CanonicalParty(
        message_id="ISO_001",
        field_type="50F",
        role="debtor",
        name=["PHILIPS MARK"],
        address_lines=["HOOGSTRAAT 6", "APT 6C"],
        country_town=CountryTown(country="BE", town="ANTWERPEN", postal_code="2000"),
        dob=DateOfBirth(year="1972", month="08", day="30"),
        pob=PlaceOfBirth(country="BE", city="BRUSSELS"),
        national_id="123456789",
        party_id=PartyIdentifier(code="NIDN", country="BE", issuer="BE", identifier="123456789"),
        is_org=False,
        meta=CanonicalMeta(source_format="50F", parse_confidence=0.95),
        fragmented_addresses=[
            FragmentedAddress(
                strt_nm="HOOGSTRAAT",
                bldg_nb="6",
                room="APT 6C",
                pst_cd="2000",
                twn_nm="ANTWERPEN",
                ctry="BE",
                fragmentation_confidence=0.92,
            )
        ],
    )

    payload = build_iso20022_party_payload(party)

    assert payload["Nm"] == "PHILIPS MARK"
    assert payload["PstlAdr"]["StrtNm"] == "HOOGSTRAAT"
    assert payload["PstlAdr"]["BldgNb"] == "6"
    assert payload["PstlAdr"]["TwnNm"] == "ANTWERPEN"
    assert payload["PstlAdr"]["Ctry"] == "BE"
    assert "TwnLctnNm" not in payload["PstlAdr"]
    assert "AdrLine" not in payload["PstlAdr"]
    assert payload["Id"]["PrvtId"]["Othr"][0]["Id"] == "123456789"
    assert payload["Id"]["PrvtId"]["DtAndPlcOfBirth"]["BirthDt"] == "1972-08-30"
    assert payload["CtryOfRes"] == "BE"
    assert validate_iso20022_party_payload(payload) == []


def test_build_iso20022_xml_for_organisation_party():
    party = CanonicalParty(
        message_id="ISO_002",
        field_type="59",
        role="creditor",
        name=["SOCIETE DIMA VOYAGES"],
        address_lines=["RUE MOHAMED ALI IMMEUBLE"],
        country_town=CountryTown(country="TN", town="SOUSSE", postal_code="4000"),
        org_id=PartyIdentifier(code="CUST", country="TN", issuer="TN", identifier="MAT123"),
        is_org=True,
        meta=CanonicalMeta(source_format="59", parse_confidence=0.88),
        fragmented_addresses=[
            FragmentedAddress(
                strt_nm="RUE MOHAMED ALI",
                bldg_nm="IMMEUBLE",
                pst_cd="4000",
                twn_nm="SOUSSE",
                ctry="TN",
                fragmentation_confidence=0.92,
            )
        ],
    )

    xml_text, payload, errors = build_iso20022_party_xml(party, role_tag="Cdtr")

    assert errors == []
    assert payload["Id"]["OrgId"]["Othr"][0]["Id"] == "MAT123"
    assert "<Cdtr>" in xml_text
    assert "<Nm>SOCIETE DIMA VOYAGES</Nm>" in xml_text
    assert "<BldgNm>IMMEUBLE</BldgNm>" in xml_text
    assert "<Ctry>TN</Ctry>" in xml_text
    assert "<AdrLine>" not in xml_text


def test_build_iso20022_payload_preserves_structured_50f_details():
    party = CanonicalParty(
        message_id="ISO_003",
        field_type="50F",
        role="debtor",
        raw="\n".join(
            [
                "/TN5908003000515000033732",
                "1/ETABL STABLE TEMENOS FRANCE",
                "2/24 RUE CLAUDE BERNARD",
                "3/TN/TUNIS BELVEDERE",
                "4/19870514",
                "5/TN/TUNIS",
                "6/TN/BNTETNTTXXX/CUST-778899",
                "7/TN/NID-AB123456",
                "8/BP 120",
            ]
        ),
        name=["ETABL STABLE TEMENOS FRANCE"],
        address_lines=["24 RUE CLAUDE BERNARD"],
        country_town=CountryTown(country="TN", town="TUNIS", postal_code="1000"),
        dob=DateOfBirth(raw="19870514", year="1987", month="05", day="14"),
        pob=PlaceOfBirth(country="TN", city="TUNIS"),
        org_id=PartyIdentifier(code="CUST", country="TN", issuer="BNTETNTTXXX", identifier="CUST-778899"),
        national_id="NID-AB123456",
        postal_complement="BP 120",
        is_org=True,
        meta=CanonicalMeta(source_format="50F", parse_confidence=1.0),
        fragmented_addresses=[
            FragmentedAddress(
                strt_nm="RUE CLAUDE BERNARD",
                bldg_nb="24",
                pst_cd="1000",
                twn_nm="TUNIS",
                ctry="TN",
                fragmentation_confidence=0.92,
            )
        ],
    )

    xml_text, payload, errors = build_iso20022_party_xml(party, include_envelope=True)

    assert errors == []
    assert payload["PstlAdr"]["PstBx"] == "BP 120"
    assert payload["PstlAdr"]["TwnNm"] == "TUNIS"
    assert payload["PstlAdr"]["TwnLctnNm"] == "TUNIS BELVEDERE"
    assert "AdrLine" not in payload["PstlAdr"]
    assert payload["Id"]["OrgId"]["Othr"][0]["Id"] == "CUST-778899"
    assert payload["Id"]["PrvtId"]["Othr"][0]["Id"] == "NID-AB123456"
    assert payload["Id"]["PrvtId"]["DtAndPlcOfBirth"]["BirthDt"] == "1987-05-14"
    assert payload["Id"]["PrvtId"]["DtAndPlcOfBirth"]["CityOfBirth"] == "TUNIS"
    assert "<PstBx>BP 120</PstBx>" in xml_text
    assert "<Id>NID-AB123456</Id>" in xml_text
    assert "<AdrLine>" not in xml_text


def test_build_iso20022_payload_uses_line_8_extended_identifiers():
    party = CanonicalParty(
        message_id="ISO_006",
        field_type="50F",
        role="debtor",
        name=["MANN GEORG"],
        address_lines=["LOW STREET 7"],
        country_town=CountryTown(country="DE", town="FRANKFURT"),
        party_id=PartyIdentifier(code="CUST", country="DE", issuer="ABC BANK", identifier="1234567890"),
        org_id=PartyIdentifier(code="CUST", country="DE", issuer="ABC BANK", identifier="CUST-778899000"),
        national_id="NID-AB123456890",
        is_org=False,
        meta=CanonicalMeta(source_format="50F", parse_confidence=1.0),
    )

    payload = build_iso20022_party_payload(party)

    assert payload["Id"]["PrvtId"]["Othr"][0]["Id"] == "NID-AB123456890"
    assert payload["Id"]["PrvtId"]["Othr"][1]["Id"] == "1234567890"


def test_build_iso20022_payload_does_not_duplicate_private_party_id_into_orgid():
    party = CanonicalParty(
        message_id="ISO_007",
        field_type="50F",
        role="debtor",
        name=["DUPONT MARIE CLAIRE"],
        address_lines=["25 AVENUE DES CHAMPS-ELYSEES"],
        country_town=CountryTown(country="FR", town="PARIS"),
        party_id=PartyIdentifier(code="CCPT", country="FR", issuer="FR", identifier="AB1234567Passport issued 2020"),
        is_org=False,
        meta=CanonicalMeta(source_format="50F", parse_confidence=1.0),
    )

    payload = build_iso20022_party_payload(party)

    assert "OrgId" not in payload["Id"]
    assert payload["Id"]["PrvtId"]["Othr"][0]["Id"] == "AB1234567Passport issued 2020"


def test_iso_mapper_removes_redundant_us_geo_address_line():
    party = CanonicalParty(
        message_id="ISO_004",
        field_type="50K",
        role="debtor",
        name=["JOHN DOE"],
        address_lines=["1234 ELM STREET", "NEW YORK, NY 10001"],
        country_town=CountryTown(country="US", town="NEW YORK", postal_code="10001"),
        is_org=False,
        meta=CanonicalMeta(source_format="50K", parse_confidence=0.9),
        fragmented_addresses=[
            FragmentedAddress(
                strt_nm="ELM STREET",
                bldg_nb="1234",
                ctry="US",
                fragmentation_confidence=0.92,
            ),
            FragmentedAddress(
                pst_cd="10001",
                twn_nm="NEW YORK",
                ctry_sub_div="NY",
                ctry="US",
                fragmentation_confidence=0.92,
            ),
        ],
    )

    xml_text, payload, errors = build_iso20022_party_xml(party, include_envelope=True)

    assert errors == []
    assert payload["PstlAdr"]["TwnNm"] == "NEW YORK"
    assert "AdrLine" not in payload["PstlAdr"]
    assert "<AdrLine>" not in xml_text


def test_iso_mapper_keeps_london_as_town_and_canary_wharf_as_locality():
    party = CanonicalParty(
        message_id="ISO_005",
        field_type="59",
        role="creditor",
        name=["ACME CORPORATION LTD"],
        address_lines=["45 CANARY WHARF", "LONDON E14 5AB"],
        country_town=CountryTown(country="GB", town="LONDON", postal_code="E14 5AB"),
        is_org=True,
        meta=CanonicalMeta(source_format="59", parse_confidence=0.9),
        fragmented_addresses=[
            FragmentedAddress(
                bldg_nb="45",
                twn_nm="CANARY WHARF",
                ctry="GB",
                fragmentation_confidence=0.92,
            ),
            FragmentedAddress(
                pst_cd="E14 5AB",
                twn_nm="LONDON",
                ctry="GB",
                fragmentation_confidence=0.92,
            ),
        ],
    )

    xml_text, payload, errors = build_iso20022_party_xml(party, role_tag="Cdtr", include_envelope=True)

    assert errors == []
    assert payload["PstlAdr"]["TwnNm"] == "LONDON"
    assert payload["PstlAdr"]["TwnLctnNm"] == "CANARY WHARF"
    assert payload["PstlAdr"]["AdrLine"] == ["45 CANARY WHARF"]
    assert "<TwnNm>LONDON</TwnNm>" in xml_text
    assert "<TwnLctnNm>CANARY WHARF</TwnLctnNm>" in xml_text


def test_iso_mapper_moves_us_state_to_ctry_sub_div_and_avoids_redundant_locality():
    party = CanonicalParty(
        message_id="ISO_008",
        field_type="50F",
        role="debtor",
        raw="\n".join(
            [
                "/US9876543210",
                "1/SMITH JOHN ROBERT",
                "2/789 MARKET STREET, APT 12B",
                "3/US/SAN FRANCISCO, CA 94103",
            ]
        ),
        name=["SMITH JOHN ROBERT"],
        address_lines=["789 MARKET STREET, APT 12B"],
        country_town=CountryTown(country="US", town="SAN FRANCISCO", postal_code="94103"),
        is_org=False,
        meta=CanonicalMeta(source_format="50F", parse_confidence=1.0),
        fragmented_addresses=[
            FragmentedAddress(
                strt_nm="MARKET STREET",
                bldg_nb="789",
                room="APT 12B",
                twn_nm="SAN FRANCISCO",
                ctry="US",
                fragmentation_confidence=0.92,
            )
        ],
    )

    payload = build_iso20022_party_payload(party)

    assert payload["PstlAdr"]["TwnNm"] == "SAN FRANCISCO"
    assert payload["PstlAdr"]["PstCd"] == "94103"
    assert payload["PstlAdr"]["CtrySubDvsn"] == "CA"
    assert "TwnLctnNm" not in payload["PstlAdr"]


def test_iso_mapper_parses_canada_postal_and_province_from_structured_line3():
    party = CanonicalParty(
        message_id="ISO_009",
        field_type="50F",
        role="debtor",
        raw="\n".join(
            [
                "/CA1234567890",
                "1/JANE DOE",
                "2/111 WELLINGTON ST",
                "3/CA/TORONTO, ON M5H 2N2",
            ]
        ),
        name=["JANE DOE"],
        address_lines=["111 WELLINGTON ST"],
        country_town=CountryTown(country="CA", town="TORONTO", postal_code=None),
        is_org=False,
        meta=CanonicalMeta(source_format="50F", parse_confidence=1.0),
    )

    payload = build_iso20022_party_payload(party)

    assert payload["PstlAdr"]["Ctry"] == "CA"
    assert payload["PstlAdr"]["TwnNm"] == "TORONTO"
    assert payload["PstlAdr"]["CtrySubDvsn"] == "ON"
    assert payload["PstlAdr"]["PstCd"] == "M5H 2N2"
    assert "TwnLctnNm" not in payload["PstlAdr"]
