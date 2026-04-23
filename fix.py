import re

def clean_50f_59f(party):
    if party.field_type in ["50F", "59F"]:
        if party.name:
            party.name = [re.sub(r'^[0-9]+/[A-Z]*\s*', '', n).strip() for n in party.name]
        if party.address_lines:
            party.address_lines = [re.sub(r'^[0-9]+/[A-Z]*\s*', '', a).strip() for a in party.address_lines]
    return party
