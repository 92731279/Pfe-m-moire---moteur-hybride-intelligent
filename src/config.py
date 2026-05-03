"""config.py — Configuration centrale du projet Moteur Hybride SWIFT"""

import os
import subprocess
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SAMPLES_DIR = DATA_DIR / "samples"
OUTPUTS_DIR = DATA_DIR / "outputs"
KB_DIR = DATA_DIR / "kb"

DEFAULT_ENCODING = "utf-8"

ADDRESS_KEYWORDS = {
    "RUE", "AVENUE", "AVE", "STREET", "ROAD", "ROUTE", "STRASSE", "BOULEVARD",
    "BD", "ZONE", "IND", "INDUSTRIELLE", "INDUSTRIAL", "CITE", "IMMEUBLE", "IMM",
    "APT", "APPT", "BLOC", "BLOCK", "LANE", "DRIVE", "WAY",
}

ORG_HINTS = {
    "SARL", "GMBH", "LTD", "LLC", "SA", "S.A.", "BANK", "BANQUE",
    "COMPANY", "SOCIETE", "STE", "GROUP", "GROUPE",
}

NOISE_PREFIXES = {
    "TEL", "TEL:", "FAX", "FAX:", "PHONE", "PHONE:", "MOBILE", "MOBILE:",
    "REF", "REF:", "REFERENCE", "BIC", "BIC:",
    "ATTN", "ATTN:", "C/O", "C/O:", "A L ATTENTION DE",
}

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")  # Changé de phi3:mini à qwen2.5:0.5b (plus léger)
# Augmenter le timeout
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
OLLAMA_MAX_RETRIES = int(os.getenv("OLLAMA_MAX_RETRIES", "3"))  # Augmenté de 1 à 3 pour permettre les retries


def _detect_wsl_windows_host() -> str | None:
    """Return the WSL Windows host gateway if available."""
    candidates = []

    try:
        output = subprocess.check_output(["sh", "-lc", "ip route show default 2>/dev/null | awk '/default/ {print $3; exit}'"], text=True).strip()
        if output:
            candidates.append(output)
    except Exception:
        pass

    try:
        output = subprocess.check_output(["sh", "-lc", "awk '/nameserver / {print $2; exit}' /etc/resolv.conf 2>/dev/null"], text=True).strip()
        if output:
            candidates.append(output)
    except Exception:
        pass

    for candidate in candidates:
        if candidate and candidate != "127.0.0.1":
            return f"http://{candidate}:11434"
    return None


@lru_cache(maxsize=1)
def get_ollama_base_urls() -> tuple[str, ...]:
    """Return Ollama endpoints to try in order."""
    urls = []

    env_url = os.getenv("OLLAMA_BASE_URL")
    if env_url:
        urls.append(env_url.rstrip("/"))

    for candidate in (
        "http://127.0.0.1:11434",
        "http://localhost:11434",
        _detect_wsl_windows_host(),
        "http://172.31.96.1:11434",
    ):
        if candidate and candidate not in urls:
            urls.append(candidate.rstrip("/"))

    return tuple(urls)
