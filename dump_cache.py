import json
from src.e3_slm_fallback import _slm_cache
print("CACHE SIZE:", len(_slm_cache.cache))
for k, v in _slm_cache.cache.items():
    print(f"Key: {k}")
    print(f"Val: {json.dumps(v, indent=2)}")
