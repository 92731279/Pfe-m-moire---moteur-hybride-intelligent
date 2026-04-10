"""config.py — Configuration centrale du projet Moteur Hybride SWIFT"""

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
}

OLLAMA_BASE_URL = "http://172.31.96.1:11434"
OLLAMA_MODEL = "phi3:mini"
