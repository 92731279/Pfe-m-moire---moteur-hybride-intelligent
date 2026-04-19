#!/usr/bin/env python3
"""
preload_ollama_model.py - Pré-charge le modèle Ollama pour éviter les délais initiaux
Utile à exécuter avant de lancer Streamlit
"""

import requests
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.config import OLLAMA_BASE_URL, OLLAMA_MODEL

def preload_model(url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL, timeout: int = 120) -> bool:
    """
    Pré-charge le modèle Ollama en mémoire.
    Retourne True si succès, False sinon.
    """
    print(f"🚀 Pré-chargement de {model} sur {url}...")
    print(f"   (Cela peut prendre 30-60 secondes...)")
    
    try:
        payload = {
            "model": model,
            "prompt": "Pre-loading model. This is a warm-up test.",
            "stream": False,
            "options": {
                "num_predict": 5,
                "temperature": 0.5,
            }
        }
        
        start = time.time()
        response = requests.post(
            f"{url}/api/generate",
            json=payload,
            timeout=(5, timeout)
        )
        elapsed = time.time() - start
        
        if response.status_code == 200:
            print(f"✅ Modèle pré-chargé avec succès en {elapsed:.1f}s")
            result = response.json().get('response', '')
            print(f"   Réponse test: {result[:80]}...")
            return True
        else:
            print(f"❌ Erreur HTTP {response.status_code}")
            print(f"   {response.text[:200]}")
            return False
            
    except requests.Timeout:
        print(f"❌ Timeout après {timeout}s - Ollama trop lent ou surchargé")
        return False
    except requests.ConnectionError as e:
        print(f"❌ Erreur de connexion: {e}")
        print(f"   Vérifiez que Ollama est lancé sur {url}")
        return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False


if __name__ == "__main__":
    success = preload_model()
    sys.exit(0 if success else 1)
