"""models.py — Structures de données canoniques du moteur hybride SWIFT"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# ============================================================
# E0 — Prétraitement
# ============================================================

class PreprocessMeta(BaseModel):
    detected_field_type: Optional[str] = None
    detected_language: Optional[str] = None
    entity_hint: str = "unknown"
    iban_country: Optional[str] = None
    removed_noise_lines: List[str] = Field(default_factory=list)
    removed_duplicate_swift_lines: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class PreprocessResult(BaseModel):
    raw_input: str
    normalized_text: str
    lines: List[str]
    meta: PreprocessMeta


# ============================================================
# E1 — Modèle canonique de parsing
# ============================================================

class CountryTown(BaseModel):
    country: Optional[str] = None
    town: Optional[str] = None
    postal_code: Optional[str] = None


class PlaceOfBirth(BaseModel):
    country: Optional[str] = None
    city: Optional[str] = None


class PartyIdentifier(BaseModel):
    code: Optional[str] = None
    country: Optional[str] = None
    issuer: Optional[str] = None
    identifier: Optional[str] = None


class CanonicalMeta(BaseModel):
    source_format: Optional[str] = None
    parse_confidence: float = 0.0
    warnings: List[str] = Field(default_factory=list)
    llm_signals: List[str] = Field(default_factory=list)
    fallback_used: bool = False


class CanonicalParty(BaseModel):
    message_id: str
    field_type: str
    role: str

    account: Optional[str] = None
    party_id: Optional[PartyIdentifier] = None
    name: List[str] = []
    address_lines: List[str] = []

    country_town: Optional[CountryTown] = None

    dob: Optional[str] = None
    pob: Optional[PlaceOfBirth] = None
    org_id: Optional[PartyIdentifier] = None
    national_id: Optional[str] = None
    postal_complement: Optional[str] = None

    is_org: Optional[bool] = None

    meta: CanonicalMeta

    address_validation: Optional[List[Dict]] = None
