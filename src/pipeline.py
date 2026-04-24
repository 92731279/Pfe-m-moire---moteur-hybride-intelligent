"""pipeline.py — Orchestration complète du moteur hybride SWIFT"""

from src.e0_preprocess import preprocess
from src.e1_parser import parse_field
from src.e2_validator import validate_party_semantics
from src.e2_address_fragmentation import fragment_party_address
from src.e3_slm_fallback import needs_slm_fallback, apply_slm_fallback
from src.pipeline_logger import PipelineLogger
from src.rejection_policy import apply_rejection_policy


def _select_best_geo_fragment(party):
    fragments = list(getattr(party, "fragmented_addresses", []) or [])
    if not fragments:
        return None

    def _score(frag):
        score = 0.0
        if getattr(frag, "twn_nm", None):
            score += 4.0
        if getattr(frag, "pst_cd", None):
            score += 3.0
        if getattr(frag, "ctry_sub_div", None):
            score += 1.0
        if getattr(frag, "bldg_nb", None) or getattr(frag, "strt_nm", None):
            score -= 1.5
        score += float(getattr(frag, "fragmentation_confidence", 0.0) or 0.0)
        return score

    candidates = [frag for frag in fragments if getattr(frag, "twn_nm", None) or getattr(frag, "pst_cd", None)]
    if not candidates:
        return None
    return max(candidates, key=_score)


def _recalibrate_confidence_after_slm(party):
    """Remonte la confiance si le fallback SLM est confirmé par les validations aval."""
    if not getattr(party.meta, "fallback_used", False):
        return party

    warnings = list(getattr(party.meta, "warnings", []) or [])
    llm_signals = set(getattr(party.meta, "llm_signals", []) or [])
    if "slm_applied" not in llm_signals:
        return party

    current = float(getattr(party.meta, "parse_confidence", 0.0) or 0.0)
    geo = getattr(party, "country_town", None)
    valid_addresses = [
        item for item in (getattr(party, "address_validation", []) or [])
        if item.get("contextual_valid")
    ]
    best_fragmentation = max(
        (float(getattr(frag, "fragmentation_confidence", 0.0) or 0.0)
         for frag in (getattr(party, "fragmented_addresses", []) or [])),
        default=0.0,
    )

    recovered_from_empty_parse = "no_content_after_account" in warnings
    geonames_exact = any("pass1_town_confirmed_geonames:exact" in str(w) for w in warnings)
    geonames_alt = any("pass1_town_confirmed_geonames:alternate" in str(w) for w in warnings)

    floor = current
    if geo and geo.country and geo.town:
        floor = max(floor, 0.58 if recovered_from_empty_parse else 0.50)
    if geo and geo.postal_code:
        floor = max(floor, 0.62)
    if geonames_alt:
        floor = max(floor, 0.72)
    if geonames_exact:
        floor = max(floor, 0.76)
    if valid_addresses:
        floor = max(floor, 0.74)
    if best_fragmentation >= 0.80:
        floor = max(floor, 0.78 if geonames_exact else 0.75)

    bonus = 0.0
    if geo and geo.country and geo.town:
        bonus += 0.05
    if geo and geo.postal_code:
        bonus += 0.03
    if geonames_alt:
        bonus += 0.05
    if geonames_exact:
        bonus += 0.07
    if valid_addresses:
        bonus += min(0.04, 0.02 * len(valid_addresses))
    if best_fragmentation >= 0.80:
        bonus += 0.03

    party.meta.parse_confidence = round(min(0.90, max(floor, current + bonus)), 2)
    return party


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
        geo_frag = _select_best_geo_fragment(e2)
        if geo_frag and geo_frag.fragmentation_confidence > 0.8:
            if not e2.country_town.town and geo_frag.twn_nm and str(geo_frag.twn_nm).upper() not in ["AVENUE", "RUE", "BOULEVARD", "STREET", "ZONE INDUSTRIELLE"]:
                e2.country_town.town = geo_frag.twn_nm
                e2.meta.warnings.append(f"pass2_town_backfilled_from_fragmentation:{geo_frag.twn_nm}")
                e2.meta.parse_confidence = min(0.9, e2.meta.parse_confidence + 0.15)
            if not e2.country_town.postal_code and geo_frag.pst_cd:
                e2.country_town.postal_code = geo_frag.pst_cd

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
            geo_frag = _select_best_geo_fragment(e2)
            if geo_frag and geo_frag.fragmentation_confidence > 0.8:
                if not e2.country_town.town and geo_frag.twn_nm and str(geo_frag.twn_nm).upper() not in ["AVENUE", "RUE", "BOULEVARD", "STREET", "ZONE INDUSTRIELLE"]:
                    e2.country_town.town = geo_frag.twn_nm
                    e2.meta.warnings.append(f"pass2_town_backfilled_from_fragmentation:{geo_frag.twn_nm}")
                    # ✅ CORRECTION: Épurer les marqueurs de quarantaine car on a récupéré une ville fiable post-SLM
                    e2.meta.warnings[:] = [w for w in e2.meta.warnings if "requires_manual_verification" not in str(w)]
                if not e2.country_town.postal_code and geo_frag.pst_cd:
                    e2.country_town.postal_code = geo_frag.pst_cd

        e2 = _recalibrate_confidence_after_slm(e2)

        logger.log(
            "E2B", "Revalidation terminée",
            confidence=e2.meta.parse_confidence,
            warnings=e2.meta.warnings,
        )

    # --- GEO-KNOWLEDGE : Backfill prudent depuis le postal explicite uniquement ---
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
        
        # Mapping inversé pour déduire le code postal depuis la ville
        reverse_mapping_tn = {
            "TUNIS": "1000", "ARIANA": "2080", "ARYANAH": "2080", "SFAX": "3000", "SOUSSE": "4000", 
            "NABEUL": "8000", "MONTPLAISIR": "1073", "LES BERGES DU LAC": "1053", 
            "BARDO": "2000", "LA MARSA": "2070", "MONASTIR": "5000", 
            "GABES": "6000", "HAMMAM SOUSSE": "4011", "CARTHAGE": "2016",
            "SUKRAH": "2036", "LA SOUKRA": "2036", "SOUKRA": "2036"
        }
        
        # Mapping inversé pour déduire le code postal depuis la ville
        reverse_mapping_tn = {
            "TUNIS": "1000", "ARIANA": "2080", "ARYANAH": "2080", "SFAX": "3000", "SOUSSE": "4000", 
            "NABEUL": "8000", "MONTPLAISIR": "1073", "LES BERGES DU LAC": "1053", 
            "BARDO": "2000", "LA MARSA": "2070", "MONASTIR": "5000", 
            "GABES": "6000", "HAMMAM SOUSSE": "4011", "CARTHAGE": "2016",
            "SUKRAH": "2036", "LA SOUKRA": "2036", "SOUKRA": "2036"
        }
        
        if c == "TN" and p:
            import re
            clean_p = re.sub(r"[^\d]", "", str(p))
            if clean_p in mapping_tn:
                if not t or str(t).strip() == "" or str(t).lower() == "none":
                    party.country_town.town = mapping_tn[clean_p]
                    if not party.meta.warnings: party.meta.warnings = []
                    party.meta.warnings.append(f"geo_postal_resolution_{clean_p}")
                    t = party.country_town.town # Mise à jour locale
        
        # 🧹 CLEANUP FINAL AVANT RETOUR: Si la ville est connue, on vire TOUT 'requires_manual_verification:town_unverified'
        if party.country_town and party.country_town.town and str(party.country_town.town).strip().upper() not in ["", "N A", "N/A", "NULL", "NONE"]:
            party.meta.warnings[:] = [w for w in party.meta.warnings if "requires_manual_verification:town_unverified" not in str(w)]
            party.meta.warnings[:] = [w for w in party.meta.warnings if "pass1_town_ambiguous_requires_disambiguation" not in str(w)]
                
        return party

    e2 = _enrich_city_via_postal(e2)

    e2 = apply_rejection_policy(e2)
    logger.log(
        "DECISION", "Décision métier",
        rejected=e2.meta.rejected,
        rejection_reasons=e2.meta.rejection_reasons,
    )


    logger.log("OUTPUT", "Pipeline terminé")

    # 🧹 CLEANUP POST-IA pour 50F/59F: Retirer les tags "1/", "2/", "3/" réinjectés par erreur
    if getattr(e2.meta, "detected_field_type", "") in ["50F", "59F"] or getattr(e0.meta, "detected_field_type", "") in ["50F", "59F"]:
        import re
        if e2.name:
            e2.name = [re.sub(r'^[0-9]+/', '', n).strip() for n in e2.name]
        if e2.address_lines:
            e2.address_lines = [re.sub(r'^[0-9]+/', '', a).strip() for a in e2.address_lines]
        if getattr(e2, "fragmented_addresses", []):
            for frag in e2.fragmented_addresses:
                if getattr(frag, "bldg_nb", None):
                    frag.bldg_nb = re.sub(r'^[0-9]+/', '', frag.bldg_nb).strip()
                if getattr(frag, "adr_line", None):
                    frag.adr_line = [re.sub(r'^[0-9]+/', '', a).strip() for a in frag.adr_line]

    return e2, e0
