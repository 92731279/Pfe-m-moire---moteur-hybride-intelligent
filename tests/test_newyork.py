import sys
from src.e2_validator import validate_party_semantics
from src.models import CanonicalParty, CountryTown, CanonicalMeta
import pprint

party = CanonicalParty(
    role="BENEFICIARY",
    name="JOHN SMITH",
    address_lines=["123 MAIN ST", "NEW YORK"],
    country_town=CountryTown(country="US", town="NEW YORK"),
    meta=CanonicalMeta(source="test", match_method="test", rule_applied="test")
)
res = validate_party_semantics(party)
pprint.pprint(res.model_dump())
