"""models.py — Structures de données canoniques du moteur hybride SWIFT"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict


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


class DateOfBirth(BaseModel):
    """Date de naissance avec composants"""
    raw: Optional[str] = None
    year: Optional[str] = None
    month: Optional[str] = None
    day: Optional[str] = None


class PartyIdentifier(BaseModel):
    code: Optional[str] = None
    country: Optional[str] = None
    issuer: Optional[str] = None
    identifier: Optional[str] = None


class CanonicalMeta(BaseModel):
    source_format: Optional[str] = None
    parse_confidence: float = 0.0
    warnings: List[str] = Field(default_factory=list)
    warnings_before_slm: List[str] = Field(default_factory=list)
    warnings_after_slm: List[str] = Field(default_factory=list)
    llm_signals: List[str] = Field(default_factory=list)
    fallback_used: bool = False
    rejected: bool = False
    rejection_reasons: List[str] = Field(default_factory=list)
    
    # 🔹 POINT D : Audit Trail & Fiabilité en Production
    requires_manual_review: bool = False


class CanonicalParty(BaseModel):
    message_id: str
    field_type: str
    role: str

    raw: Optional[str] = None
    account: Optional[str] = None
    party_id: Optional[PartyIdentifier] = None
    name: List[str] = Field(default_factory=list)
    address_lines: List[str] = Field(default_factory=list)

    country_town: Optional[CountryTown] = None

    dob: Optional[DateOfBirth] = None
    pob: Optional[PlaceOfBirth] = None
    org_id: Optional[PartyIdentifier] = None
    national_id: Optional[str] = None
    postal_complement: Optional[str] = None

    is_org: Optional[bool] = None

    meta: CanonicalMeta
    address_validation: Optional[List[Dict]] = None
    
    # 🔹 NOUVEAU : Résultat de la fragmentation E2.5
    fragmented_addresses: List["FragmentedAddress"] = Field(default_factory=list)


# ============================================================
# E2.5 — Fragmentation d'adresse (ISO 20022 mapping)
# ============================================================

class FragmentedAddress(BaseModel):
    # ⚠️ AJOUTER CETTE LIGNE pour accepter les deux formats de noms
    model_config = ConfigDict(populate_by_name=True)
    
    strt_nm: Optional[str] = Field(None, alias="StrtNm")
    bldg_nb: Optional[str] = Field(None, alias="BldgNb")
    bldg_nm: Optional[str] = Field(None, alias="BldgNm")
    flr: Optional[str] = Field(None, alias="Flr")
    room: Optional[str] = Field(None, alias="Room")
    pst_cd: Optional[str] = Field(None, alias="PstCd")
    twn_nm: Optional[str] = Field(None, alias="TwnNm")
    ctry_sub_div: Optional[str] = Field(None, alias="CtrySubDvsn")
    ctry: Optional[str] = Field(None, alias="Ctry")
    
    # Fallback XSD garanti si la fragmentation échoue
    adr_line: List[str] = Field(default_factory=list)  
    
    fragmentation_confidence: float = 0.0
    fallback_used: bool = False
