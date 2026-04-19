#!/usr/bin/env python3
"""
monitor_ollama.py - Diagnostic Ollama et troubleshooting
"""

import requests
import sys
import time
from pathlib import Path
from typing import Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import OLLAMA_BASE_URL, OLLAMA_MODEL


def check_connection(url: str = OLLAMA_BASE_URL) -> bool:
    """Vérifie si Ollama est accessible"""
    print("🔗 Vérification de la connexion...")
    try:
        r = requests.get(f"{url}/api/tags", timeout=5)
        if r.status_code == 200:
            print(f"✅ Ollama accessible sur {url}")
            return True
        else:
            print(f"❌ Ollama retourne {r.status_code}")
            return False
    except requests.ConnectionError:
        print(f"❌ Impossible de se connecter à {url}")
        return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


def check_models(url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL) -> Dict[str, Any]:
    """Liste les modèles disponibles"""
    print("📦 Modèles disponibles...")
    try:
        r = requests.get(f"{url}/api/tags", timeout=5)
        if r.status_code != 200:
            print(f"❌ Erreur {r.status_code}")
            return {}
        
        data = r.json()
        models = data.get('models', [])
        
        if not models:
            print("❌ Aucun modèle trouvé!")
            return {}
        
        result = {}
        for m in models:
            name = m.get('name')
            size_bytes = m.get('size', 0)
            size_gb = size_bytes / (1024**3)
            
            status = "✅" if name == model else "  "
            print(f"{status} {name:<20} ({size_gb:.2f} GB)")
            result[name] = size_gb
        
        if model not in result:
            print(f"⚠️  Modèle configuré '{model}' NON TROUVÉ!")
        
        return result
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return {}


def test_generate_endpoint(url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL, iterations: int = 3) -> Dict[str, Any]:
    """Teste l'endpoint /api/generate"""
    print(f"🧪 Test /api/generate ({iterations} appels)...")
    
    results = {
        'success': 0,
        'failures': 0,
        'errors': {},
        'times': []
    }
    
    for i in range(iterations):
        try:
            payload = {
                "model": model,
                "prompt": "Hello",
                "stream": False,
                "options": {"num_predict": 10}
            }
            
            start = time.time()
            r = requests.post(
                f"{url}/api/generate",
                json=payload,
                timeout=(3, 30)
            )
            elapsed = time.time() - start
            results['times'].append(elapsed)
            
            if r.status_code == 200:
                results['success'] += 1
                print(f"  ✅ Appel {i+1}: {elapsed:.2f}s")
            else:
                results['failures'] += 1
                status = r.status_code
                if status not in results['errors']:
                    results['errors'][status] = 0
                results['errors'][status] += 1
                print(f"  ❌ Appel {i+1}: HTTP {status}")
                
        except requests.Timeout:
            results['failures'] += 1
            results['errors']['timeout'] = results['errors'].get('timeout', 0) + 1
            print(f"  ⏱️  Appel {i+1}: TIMEOUT")
        except Exception as e:
            results['failures'] += 1
            etype = str(type(e).__name__)
            results['errors'][etype] = results['errors'].get(etype, 0) + 1
            print(f"  ❌ Appel {i+1}: {e}")
        
        time.sleep(1)
    
    return results


def full_diagnostic(url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL) -> bool:
    """Diagnostic complet"""
    print("\n" + "="*60)
    print(" 🔍 DIAGNOSTIC OLLAMA COMPLET")
    print("="*60 + "\n")
    
    # 1. Connexion
    if not check_connection(url):
        print("\n❌ DIAGNOSTIC ÉCHOUÉ: Ollama n'est pas accessible")
        return False
    print()
    
    # 2. Modèles
    models = check_models(url, model)
    if not models:
        return False
    print()
    
    # 3. Test /api/generate
    gen_results = test_generate_endpoint(url, model, iterations=3)
    print(f"  Succès: {gen_results['success']}/3")
    if gen_results['times']:
        avg_time = sum(gen_results['times']) / len(gen_results['times'])
        print(f"  Temps moyen: {avg_time:.2f}s")
    if gen_results['errors']:
        print(f"  Erreurs: {gen_results['errors']}")
    print()
    
    # 4. Diagnostic
    print("📋 DIAGNOSTIC:")
    if gen_results['success'] == 3:
        print("✅ Ollama fonctionne normalement")
        print("   Les erreurs HTTP 500 viennent peut-être d'appels concurrents")
    elif gen_results['success'] >= 1:
        print("⚠️  Ollama est instable")
        print("   Certains appels réussissent, d'autres échouent")
    else:
        print("❌ Ollama ne répond pas correctement")
        print("   Tous les appels ont échoué")
    
    print("\n" + "="*60 + "\n")
    return True


if __name__ == "__main__":
    success = full_diagnostic()
    sys.exit(0 if success else 1)
