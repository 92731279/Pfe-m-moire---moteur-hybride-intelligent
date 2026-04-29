import re

with open("src/e3_slm_fallback.py", "r") as f:
    content = f.read()

# Make sure that if the slm fallback returns a postal code as city we reject the fallback city! 
if "def run_slm_fallback" in content:
    print("Has slm fallback")

