"""Utilities to extract party fields from a full SWIFT FIN message."""

from __future__ import annotations

import re
from typing import Dict, List, Optional


FIELD_START_RE = re.compile(r"^\s*:([0-9]{2}[A-Z]?):(.*)$")
PARTY_TAGS = {"50F", "50K", "59F", "59"}


def clean_swift_message(raw_message: str) -> str:
    """Remove common FIN transport/control wrappers while keeping field content."""
    text = (raw_message or "").replace("\x01", "").replace("\x03", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"^\s*\{4:\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n\s*-\}\s*$", "", text)
    text = re.sub(r"\s*-\}\s*$", "", text)
    return text.strip()


def extract_swift_fields(raw_message: str) -> List[Dict[str, object]]:
    """
    Extract SWIFT fields from a complete FIN message.

    A field starts on a line like ``:50F:`` and continues until the next field
    tag. Header blocks such as ``{1:...}``, ``{2:...}``, ``{3:...}`` are kept
    outside the extracted values.
    """
    text = clean_swift_message(raw_message)
    fields: List[Dict[str, object]] = []
    current: Optional[Dict[str, object]] = None

    for line_no, line in enumerate(text.splitlines(), start=1):
        match = FIELD_START_RE.match(line)
        if match:
            if current:
                fields.append(current)
            tag, first_value = match.groups()
            current = {
                "tag": tag.upper(),
                "value": first_value.strip(),
                "lines": [first_value.strip()] if first_value.strip() else [],
                "line_no": line_no,
            }
            continue

        if current is None:
            continue

        cleaned_line = line.strip()
        if cleaned_line:
            current["lines"].append(cleaned_line)

    if current:
        fields.append(current)

    return fields


def build_raw_party_field(field: Dict[str, object]) -> str:
    """Rebuild one party field in the format expected by the existing engine."""
    tag = str(field.get("tag") or "").upper()
    lines = [str(line) for line in field.get("lines") or []]
    if not lines:
        value = str(field.get("value") or "").strip()
        lines = [value] if value else []
    return f":{tag}:" + ("\n" + "\n".join(lines) if lines else "")


def extract_party_fields(raw_message: str) -> List[Dict[str, object]]:
    """Return only 50F/50K/59F/59 fields with debtor/creditor role metadata."""
    parties = []
    for field in extract_swift_fields(raw_message):
        tag = str(field.get("tag") or "").upper()
        if tag not in PARTY_TAGS:
            continue
        enriched = dict(field)
        enriched["role"] = "debtor" if tag.startswith("50") else "creditor"
        enriched["role_label"] = "Debtor" if tag.startswith("50") else "Creditor"
        enriched["raw_party_field"] = build_raw_party_field(field)
        parties.append(enriched)
    return parties
