"""pipeline.py — Orchestration complète du moteur hybride SWIFT"""

from src.e0_preprocess import preprocess
from src.e1_parser import parse_field
from src.e2_validator import validate_party_semantics
from src.e2_address_fragmentation import fragment_party_address
from src.e3_slm_fallback import needs_slm_fallback, apply_slm_fallback
from src.pipeline_logger import PipelineLogger
from src.rejection_policy import apply_rejection_policy


def run_pipeline(
    raw_message: str,
    message_id: str = "MSG_PIPELINE",
    slm_model: str = "qwen2.5:0.5b",
    logger: PipelineLogger = None,
):
    logger = logger or PipelineLogger()

    logger.log("INPUT", "Message reçu", chars=len(raw_message or ""))

    # E0 — Prétraitement
    logger.log("E0", "Début prétraitement")
    e0 = preprocess(raw_message)
    logger.log(
        "E0", "Prétraitement terminé",
        field_type=e0.meta.detected_field_type,
        iban_country=e0.meta.iban_country,
        entity_hint=e0.meta.entity_hint,
        lines=len(e0.lines),
    )

    # E1 — Parsing
    logger.log("E1", "Début parsing")
    e1 = parse_field(e0, message_id=message_id)
    logger.log(
        "E1", "Parsing terminé",
        confidence=e1.meta.parse_confidence,
        warnings=len(e1.meta.warnings),
        name=e1.name,
        address_lines=e1.address_lines,
        country=e1.country_town.country if e1.country_town else None,
        town=e1.country_town.town if e1.country_town else None,
    )

    # E2 — Validation sémantique
    logger.log("E2", "Début validation sémantique")
    e2 = validate_party_semantics(e1)
    logger.log(
        "E2", "Validation sémantique terminée",
        confidence=e2.meta.parse_confidence,
        warnings=e2.meta.warnings,
    )

    # E2.5 — Fragmentation d'adresse (NOUVEAU)
    logger.log("E2.5", "Début fragmentation adresse")
    e2 = fragment_party_address(e2)
    
    # --- BACKFILL depuis Fragmentation si E1 a échoué ---
    if getattr(e2, 'fragmented_addresses', []) and e2.country_town:
        for frag in e2.fragmented_addresses:
            if frag.fragmentation_confidence > 0.8:
                if not e2.country_town.town and frag.twn_nm and str(frag.twn_nm).upper() not in ["AVENUE", "RUE", "BOULEVARD", "STREET", "ZONE INDUSTRIELLE"]:
                    e2.country_town.town = frag.twn_nm
                    e2.meta.warnings.append(f"pass2_town_backfilled_from_fragmentation:{frag.twn_nm}")
                    e2.meta.parse_confidence = min(0.9, e2.meta.parse_confidence + 0.15)
                if not e2.country_town.postal_code and frag.pst_cd:
                    e2.country_town.postal_code = frag.pst_cd

    logger.log(
        "E2.5", "Fragmentation terminée",
        fragmented_count=len(getattr(e2, 'fragmented_addresses', [])),
        confidence_avg=(
            sum(addr.fragmentation_confidence 
                for addr in getattr(e2, 'fragmented_addresses', [])) 
            / len(getattr(e2, 'fragmented_addresses', []))
            if getattr(e2, 'fragmented_addresses', []) else 0.0
        ),
    )

    # E3 — SLM Fallback
    use_slm = needs_slm_fallback(e2)
    logger.log("E3", "Décision fallback SLM", use_slm=use_slm)

    if use_slm:
        logger.log("E3", "Appel SLM en cours", model=slm_model)
        e2 = apply_slm_fallback(e2, model=slm_model)
        logger.log(
            "E3", "SLM terminé",
            llm_signals=e2.meta.llm_signals,
            fallback_used=e2.meta.fallback_used,
        )

        logger.log("E2B", "Revalidation après SLM")
        e2 = validate_party_semantics(e2)
        
        # Re-fragmentation après SLM si nécessaire
        logger.log("E2.5B", "Re-fragmentation après SLM")
        e2 = fragment_party_address(e2)
        
        # --- BACKFILL depuis Fragmentation (Post-SLM) ---
        if getattr(e2, 'fragmented_addresses', []) and e2.country_town:
            for frag in e2.fragmented_addresses:
                if frag.fragmentation_confidence > 0.8:
                    if not e2.country_town.town and frag.twn_nm and str(frag.twn_nm).upper() not in ["AVENUE", "RUE", "BOULEVARD", "STREET", "ZONE INDUSTRIELLE"]:
                        e2.country_town.town = frag.twn_nm
                        e2.meta.warnings.append(f"pass2_town_backfilled_from_fragmentation:{frag.twn_nm}")
                    if not e2.country_town.postal_code and frag.pst_cd:
                        e2.country_town.postal_code = frag.pst_cd

        logger.log(
            "E2B", "Revalidation terminée",
            confidence=e2.meta.parse_confidence,
            warnings=e2.meta.warnings,
        )

    # --- GEO-KNOWLEDGE : Résolution Postale Implicite ---
    def _enrich_city_via_postal(party):
        if not party.country_town: return party
        t = party.country_town.town
        p = party.country_town.postal_code
        c = party.country_town.country
        
        if not p and party.fragmented_addresses:
            for frag in party.fragmented_addresses:
                if frag.pst_cd:
                    p = frag.pst_cd
                    party.country_town.postal_code = p
                    break
        
        mapping_tn = {
            "2037": "ENNASR / ARIANA", "1000": "TUNIS", "2080": "ARIANA",
            "3000": "SFAX", "4000": "SOUSSE", "8000": "NABEUL",
            "1073": "MONTPLAISIR", "1053": "LES BERGES DU LAC", "2000": "BARDO",
            "2070": "LA MARSA", "2078": "LA MARSA", "5000": "MONASTIR",
            "6000": "GABES", "4011": "HAMMAM SOUSSE", "2016": "CARTHAGE"
        }
        
        if c == "TN" and p:
            import re
            clean_p = re.sub(r"[^\d]", "", str(p))
            if clean_p in mapping_tn:
                if not t or str(t).strip() == "" or str(t).lower() == "none":
                    party.country_town.town = mapping_tn[clean_p]
                    if not party.meta.warnings: party.meta.warnings = []
                    party.meta.warnings.append(f"geo_postal_resolution_{clean_p}")
        return party

    e2 = _enrich_city_via_postal(e2)

    e2 = apply_rejection_policy(e2)
    logger.log(
        "DECISION", "Décision métier",
        rejected=e2.meta.rejected,
        rejection_reasons=e2.meta.rejection_reasons,
    )

    logger.log("OUTPUT", "Pipeline terminé")
    return e2, logger