from src.pipeline import run_pipeline
msg = ":59:/123456 MONSIEUR BOURGUIBA HABIB RUE DE LA LIBERTE APPT 4B NABEUL TUNISIE"
res, _ = run_pipeline(msg)
print("Account:", res.account)
print("Postal code in country_town:", res.country_town.postal_code if res.country_town else None)
if res.fragmented_addresses:
    print("Postal code in frag:", getattr(res.fragmented_addresses[0], 'pst_cd', None))
