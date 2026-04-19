"""e0_preprocess.py — Étape E0 : Prétraitement du message SWIFT brut"""

import re
import unicodedata
from typing import Optional

from src.config import ADDRESS_KEYWORDS, NOISE_PREFIXES, ORG_HINTS
from src.logger import StepLogger
from src.models import PreprocessMeta, PreprocessResult

FIELD_TAG_PATTERN = re.compile(r"^\s*:?(50F|50K|59F|59):", re.IGNORECASE)
IBAN_PATTERN = re.compile(r"\b([A-Z]{2})\d{2}[A-Z0-9]{8,30}\b", re.IGNORECASE)
SWIFT_STRUCTURED_PREFIX_PATTERN = re.compile(r"^[1-8]/")


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_whitespace(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(lines)


def _detect_field_type(raw: str) -> Optional[str]:
    match = FIELD_TAG_PATTERN.match(raw.strip())
    if match:
        return match.group(1).upper()
    if SWIFT_STRUCTURED_PREFIX_PATTERN.search(raw):
        return "50F"
    return None


def _remove_field_prefix(raw: str) -> str:
    return FIELD_TAG_PATTERN.sub("", raw.strip(), count=1).strip()


def _extract_iban_country(text: str) -> Optional[str]:
    match = IBAN_PATTERN.search(text.upper())
    if match:
        return match.group(1).upper()
    return None


def _remove_noise_lines(lines: list, meta: PreprocessMeta, log: StepLogger) -> list:
    kept = []
    for line in lines:
        upper = line.upper()
        is_noise = False
        for prefix in NOISE_PREFIXES:
            if upper.startswith(prefix):
                meta.removed_noise_lines.append(line)
                log.warn(f"Ligne de bruit supprimée: {line}")
                is_noise = True
                break
        if not is_noise:
            kept.append(line)
    return kept


def _deduplicate_structured_lines(lines: list, meta: PreprocessMeta, log: StepLogger) -> list:
    seen = set()
    result = []
    for line in lines:
        if SWIFT_STRUCTURED_PREFIX_PATTERN.match(line):
            if line in seen:
                meta.removed_duplicate_swift_lines.append(line)
                log.warn(f"Ligne SWIFT dupliquée supprimée: {line}")
                continue
            seen.add(line)
        result.append(line)
    return result


def _detect_language(lines: list) -> str:
    text = " ".join(lines).upper()
    french_markers = {"RUE", "AVENUE", "BOULEVARD", "SOCIETE", "BANQUE", "ZONE"}
    german_markers = {"STRASSE", "GMBH"}
    english_markers = {"STREET", "ROAD", "LANE", "COMPANY"}
    if any(m in text for m in french_markers):
        return "fr"
    if any(m in text for m in german_markers):
        return "de"
    if any(m in text for m in english_markers):
        return "en"
    return "unknown"


def _detect_entity_hint(lines: list) -> str:
    joined = " ".join(lines).upper()
    if any(token in joined for token in ORG_HINTS):
        return "OrgId"
    tokens = joined.split()
    if len(tokens) >= 2 and all(t.isalpha() or "." in t for t in tokens[:3]):
        return "PrvtId"
    return "unknown"


def preprocess(raw_input: str, logger: Optional[StepLogger] = None) -> PreprocessResult:
    log = logger or StepLogger(enabled=False)
    meta = PreprocessMeta()

    log.info("Début E0 prétraitement")

    if not raw_input or not raw_input.strip():
        meta.warnings.append("empty_input")
        log.warn("Entrée vide")
        return PreprocessResult(raw_input=raw_input, normalized_text="", lines=[], meta=meta)

    detected_field_type = _detect_field_type(raw_input)
    meta.detected_field_type = detected_field_type
    if detected_field_type:
        log.ok(f"Type détecté: {detected_field_type}")
    else:
        log.warn("Type non détecté automatiquement")

    text = _remove_field_prefix(raw_input)
    log.info("Préfixe SWIFT supprimé si présent")

    text = _strip_accents(text)
    log.info("Accents supprimés")

    text = _normalize_whitespace(text)
    log.info("Espaces et sauts de ligne normalisés")

    lines = [line for line in text.split("\n") if line.strip()]
    log.ok(f"Lignes après normalisation: {len(lines)}")

    meta.iban_country = _extract_iban_country(text)
    if meta.iban_country:
        log.ok(f"Pays IBAN détecté: {meta.iban_country}")

    lines = _remove_noise_lines(lines, meta, log)
    lines = _deduplicate_structured_lines(lines, meta, log)

    meta.detected_language = _detect_language(lines)
    log.info(f"Langue détectée: {meta.detected_language}")

    meta.entity_hint = _detect_entity_hint(lines)
    log.info(f"Type entité probable: {meta.entity_hint}")

    normalized_text = "\n".join(lines)
    log.ok("Fin E0 prétraitement")

    return PreprocessResult(
        raw_input=raw_input,
        normalized_text=normalized_text,
        lines=lines,
        meta=meta,
    )
