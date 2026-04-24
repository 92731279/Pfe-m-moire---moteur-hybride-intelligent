from src.models import CanonicalMeta, CanonicalParty, CountryTown, FragmentedAddress
from src.quality_metrics import (
    compare_party_to_ground_truth,
    compute_dataset_precision,
    compute_reliability_score,
)


def test_compute_reliability_score_high_quality_party():
    party = CanonicalParty(
        message_id="QUAL_001",
        field_type="50F",
        role="debtor",
        name=["PHILIPS MARK"],
        address_lines=["HOOGSTRAAT 6 APT 6C"],
        country_town=CountryTown(country="BE", town="ANTWERPEN", postal_code="2000"),
        meta=CanonicalMeta(
            source_format="50F",
            parse_confidence=1.0,
            warnings=["pass1_town_confirmed_geonames:exact"],
            fallback_used=False,
            rejected=False,
        ),
        address_validation=[{"contextual_valid": True}],
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

    reliability = compute_reliability_score(party)

    assert reliability["score"] >= 0.85
    assert reliability["band"] == "Tres fiable"
    assert reliability["country_town_parsing"]["score"] == 1.0
    assert reliability["country_town_parsing"]["country_present"] is True
    assert reliability["country_town_parsing"]["town_present"] is True


def test_compute_reliability_score_exposes_country_town_parsing_metric_when_town_unverified():
    party = CanonicalParty(
        message_id="QUAL_001B",
        field_type="59",
        role="creditor",
        name=["ACME"],
        address_lines=["ZONE INDUSTRIELLE"],
        country_town=CountryTown(country="TN", town="ERRIADH", postal_code=None),
        meta=CanonicalMeta(
            source_format="59",
            parse_confidence=0.45,
            warnings=["requires_manual_verification:town_unverified"],
            fallback_used=False,
            rejected=True,
        ),
    )

    reliability = compute_reliability_score(party)

    assert reliability["country_town_parsing"]["country_present"] is True
    assert reliability["country_town_parsing"]["town_present"] is True
    assert reliability["country_town_parsing"]["score"] == 0.25
    assert reliability["reasons"]["country_town_parsing"] == "Town extracted but unverified"


def test_compare_party_to_ground_truth():
    party = CanonicalParty(
        message_id="QUAL_002",
        field_type="59",
        role="creditor",
        name=["SOCIETE DIMA VOYAGES"],
        address_lines=["RUE MOHAMED ALI IMMEUBLE"],
        country_town=CountryTown(country="TN", town="SOUSSE", postal_code="4000"),
        meta=CanonicalMeta(source_format="59", parse_confidence=0.9),
    )

    comp = compare_party_to_ground_truth(
        party,
        {
            "name": "SOCIETE DIMA VOYAGES",
            "country": "TN",
            "town": "SOUSSE",
            "postal_code": "4000",
            "address": "RUE MOHAMED ALI IMMEUBLE",
        },
    )

    assert all(comp.values())


def test_compute_dataset_precision():
    party_ok = CanonicalParty(
        message_id="QUAL_003",
        field_type="50K",
        role="debtor",
        name=["AHMED TRABELSI"],
        address_lines=["12 RUE IBN KHALDOUN"],
        country_town=CountryTown(country="TN", town="TUNIS", postal_code="1000"),
        meta=CanonicalMeta(source_format="50K", parse_confidence=0.9),
    )
    party_bad = CanonicalParty(
        message_id="QUAL_004",
        field_type="50K",
        role="debtor",
        name=["BAD NAME"],
        address_lines=["BAD ADDRESS"],
        country_town=CountryTown(country="TN", town="SFAX", postal_code="3000"),
        meta=CanonicalMeta(source_format="50K", parse_confidence=0.4),
    )

    metrics = compute_dataset_precision(
        [
            (
                party_ok,
                {
                    "name": "AHMED TRABELSI",
                    "country": "TN",
                    "town": "TUNIS",
                    "postal_code": "1000",
                    "address": "12 RUE IBN KHALDOUN",
                },
            ),
            (
                party_bad,
                {
                    "name": "AHMED TRABELSI",
                    "country": "TN",
                    "town": "TUNIS",
                    "postal_code": "1000",
                    "address": "12 RUE IBN KHALDOUN",
                },
            ),
        ]
    )

    assert metrics["count"] == 2
    assert metrics["field_accuracy"]["country"] == 1.0
    assert metrics["field_accuracy"]["name"] == 0.5
    assert metrics["exact_match_rate"] == 0.5
