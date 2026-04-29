from src.pipeline import run_pipeline
msg = ":59:/123456 MONSIEUR BOURGUIBA HABIB RUE DE LA LIBERTE APPT 4B NABEUL TUNISIE"
res, _ = run_pipeline(msg, slm_model="qwen2.5:0.5b")
print("Postal code:", res.country_town.postal_code)
