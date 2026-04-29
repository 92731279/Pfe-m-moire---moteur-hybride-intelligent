# test_ollama.py
import requests
import os

url = os.getenv("OLLAMA_BASE_URL", "http://172.31.96.1:11434")
print(f"🔗 Testing: {url}/api/tags")

try:
    # Test 1: Liste des modèles
    r = requests.get(f"{url}/api/tags", timeout=5)
    print(f"✅ /api/tags → {r.status_code}")
    print(f"   Models: {[m['name'] for m in r.json().get('models', [])]}")
    
    # Test 2: Génération minimale
    payload = {
        "model": "phi3:mini",
        "prompt": "Hello",
        "stream": False,
        "options": {"num_predict": 10}
    }
    r2 = requests.post(f"{url}/api/generate", json=payload, timeout=10)
    print(f"✅ /api/generate → {r2.status_code}")
    if r2.status_code == 200:
        print(f"   Response: {r2.json().get('response', '')[:50]}...")
    else:
        print(f"   Error: {r2.text[:200]}")
        
except Exception as e:
    print(f"❌ Error: {type(e).__name__}: {e}")