"""e3_slm_fallback.py — Étape E3 : Fallback SLM local via Ollama"""

import json
import re
import urllib.request
from typing import Dict, Optional

from src.models import CanonicalParty, CountryTown
from src.config import OLLAMA_BASE_URL, OLLAMA_MODEL
from src.reference_data import COUNTRY_NAME_TO_CODE, COUNTRY_CODES

OLLAMA_URL = f"{OLLAMA_BASE_URL}/api/generate"
DEFAULT_MODEL = OLLAMA_MODEL


def _norm(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value.strip())


def _build_prompt(party: CanonicalParty) -> str:
    country = party.country_town.country if party.country_town else ""
    town = party.country_town.town if party.country_town else ""
    return f"""
You are a strict extraction assistant.

Task:
Correct only ambiguous fields in this SWIFT party block.

Return EXACTLY 5 lines and nothing else:
NAME=...
ADDRESS=...
COUNTRY=...
TOWN=...
IS_ORG=...

Rules:
- No markdown
- No JSON
- No explanation
- No extra text
- Keep values conservative
- Do not invent new values
- If uncertain, keep original values
- ADDRESS must be one single line
- IS_ORG must be true or false
- COUNTRY must be ISO-2 if possible

INPUT:
NAME={" | ".join(party.name)}
ADDRESS={" | ".join(party.address_lines)}
COUNTRY={country}
TOWN={town}
IS_ORG={party.is_org}
WARNINGS={" | ".join(party.meta.warnings)}
""".strip()


def _call_ollama(prompt: str, model: str = DEFAULT_MODEL) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0, "num_predict": 120},
    }
    req = urllib.request.Request(
        OLLAMA_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as response:
        body = response.read().decode("utf-8")
    data = json.loads(body)
    return data.get("response", "").strip()


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    text = re.sub(r"^```[a-zA-Z0-9]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_key_value_response(text: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    cleaned = _strip_code_fences(text)
    for line in cleaned.splitlines():
        line = line.strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip().upper()] = value.strip()
    return result


def _normalize_country_value(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    raw = _norm(value).upper()
    if raw in COUNTRY_CODES:
        return raw
    return COUNTRY_NAME_TO_CODE.get(raw)


def _clean_address_value(address: Optional[str], town: Optional[str], country: Optional[str]) -> Optional[str]:
    if not address:
        return None
    cleaned = address.strip()
    variants = set()
    if town:
        variants.add(_norm(town))
        variants.add(_norm(town).upper())
    if country:
        variants.add(_norm(country))
        variants.add(_norm(country).upper())
        upper_country = _norm(country).upper()
        if upper_country in COUNTRY_CODES:
            for alias, code in COUNTRY_NAME_TO_CODE.items():
                if code == upper_country:
                    variants.add(alias)
                    variants.add(alias.upper())
    for value in variants:
        if value:
            cleaned = re.sub(rf"\b{re.escape(value)}\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*,\s*,", ",", cleaned)
    cleaned = re.sub(r"\s+,", ",", cleaned)
    cleaned = re.sub(r",\s+", ", ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    cleaned = cleaned.strip(" ,")
    return cleaned or None


def _value_is_grounded(candidate: Optional[str], party: CanonicalParty) -> bool:
    if not candidate:
        return False
    c = _norm(candidate).upper()
    if not c:
        return False
    evidence_parts = []
    evidence_parts.extend(party.name)
    evidence_parts.extend(party.address_lines)
    if party.country_town:
        if party.country_town.country:
            evidence_parts.append(party.country_town.country)
        if party.country_town.town:
            evidence_parts.append(party.country_town.town)
    evidence = " ".join(_norm(x).upper() for x in evidence_parts if x)
    if c in evidence:
        return True
    normalized_country = _normalize_country_value(candidate)
    if normalized_country and party.country_town and party.country_town.country:
        if normalized_country == _norm(party.country_town.country).upper():
            return True
    return False


def _is_better_name(current: list, candidate: Optional[str]) -> bool:
    if not candidate:
        return False
    if not current:
        return True
    current_joined = _norm(" ".join(current))
    candidate = _norm(candidate)
    if not candidate:
        return False
    return candidate.upper() != current_joined.upper()


def _is_better_address(current: list, candidate: Optional[str]) -> bool:
    if not candidate:
        return False
    if not current:
        return True
    current_joined = _norm(" | ".join(current))
    candidate = _norm(candidate)
    if not candidate:
        return False
    return candidate.upper() != current_joined.upper()


def needs_slm_fallback(party: CanonicalParty) -> bool:
    warnings = set(party.meta.warnings)

    if (
        not party.address_lines
        and party.country_town is not None
        and party.country_town.country
        and party.country_town.town
        and party.meta.parse_confidence >= 0.75
    ):
        return False

    if (
        party.address_lines
        and party.country_town is not None
        and party.country_town.country
        and party.country_town.town
        and party.meta.parse_confidence >= 0.75
    ):
        return False

    strong_triggers = [
        "name_address_mixed",
        "town_reclassified_as_address",
        "semantic_unknown_town_for_country",
        "semantic_no_valid_address_detected",
        "invalid_structured_line_3",
        "ambiguous_city_country_tail",
    ]

    if any(any(w.startswith(t) for t in strong_triggers) for w in warnings):
        return True

    if any(w.startswith("multiline_name_fused") for w in warnings):
        if party.meta.parse_confidence < 0.75:
            return True

    if party.meta.parse_confidence < 0.70:
        return True

    return False


def apply_slm_fallback(party: CanonicalParty, model: str = DEFAULT_MODEL) -> CanonicalParty:
    try:
        prompt = _build_prompt(party)
        raw_response = _call_ollama(prompt, model=model)
        parsed = _parse_key_value_response(raw_response)

        current_country = party.country_town.country if party.country_town else None
        current_town = party.country_town.town if party.country_town else None

        slm_name = parsed.get("NAME")
        slm_address = parsed.get("ADDRESS")
        slm_country_raw = parsed.get("COUNTRY")
        slm_country = _normalize_country_value(slm_country_raw)
        slm_town = parsed.get("TOWN")
        slm_is_org = parsed.get("IS_ORG")

        final_country = current_country
        final_town = current_town

        if slm_name and _value_is_grounded(slm_name, party) and _is_better_name(party.name, slm_name):
            party.name = [_norm(slm_name)]

        if slm_country:
            final_country = slm_country

        if slm_town and _value_is_grounded(slm_town, party):
            cand = _norm(slm_town)
            if current_town:
                cur = _norm(current_town)
                if cand.upper() == cur.upper() or len(cand) >= len(cur):
                    final_town = cand
            else:
                final_town = cand

        cleaned_address = _clean_address_value(
            slm_address, town=final_town, country=slm_country_raw or final_country
        )

        if party.address_lines:
            if (
                cleaned_address
                and _value_is_grounded(cleaned_address, party)
                and _is_better_address(party.address_lines, cleaned_address)
            ):
                party.address_lines = [cleaned_address]

        if final_country or final_town:
            if party.country_town is None:
                party.country_town = CountryTown(country=final_country, town=final_town, postal_code=None)
            else:
                if final_country:
                    party.country_town.country = final_country
                if final_town:
                    party.country_town.town = final_town

        if slm_is_org:
            val = _norm(slm_is_org).lower()
            if val == "true":
                party.is_org = True
            elif val == "false":
                party.is_org = False

        party.meta.fallback_used = True
        if "slm_applied" not in party.meta.llm_signals:
            party.meta.llm_signals.append("slm_applied")
        party.meta.parse_confidence = min(1.0, round(party.meta.parse_confidence + 0.05, 2))

    except Exception as e:
        err = f"slm_error:{type(e).__name__}"
        if err not in party.meta.llm_signals:
            party.meta.llm_signals.append(err)

    return party
