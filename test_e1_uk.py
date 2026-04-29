from src.e1_parser import _extract_country_postal_town_fragment, _split_embedded_country_prefix, _is_postal_town_line, CountryTown
print(_extract_country_postal_town_fragment("E14 5AB"))
print(_extract_country_postal_town_fragment("45 Canary Wharf"))
