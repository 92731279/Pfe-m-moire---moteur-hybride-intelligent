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
    disable_slm: bool = False,
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
    use_slm = needs_slm_fallback(e2) and not disable_slm
    logger.log("E3", "Décision fallback SLM", use_slm=use_slm, disabled=disable_slm)

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

    # --- GEO-KNOWLEDGE : Inférence standardisée internationale code postal → ville ---
    def _enrich_city_via_postal(party):
        """
        Enrichissement robuste: inférer la ville depuis code postal + pays.
        Standardisé pour TOUS les pays supportés via data/postal_mappings.json.
        
        Stratégie de fallback:
        1. Dictionnaire postal_mappings.json (rapide, 20+ pays)
        2. SLM fallback si dictionnaire échoue (plus lent, couvre tous les pays)
        
        Logique:
        1. Si ville est présente, garder telle quelle
        2. Si ville absente mais postal présent → inférer via mappings globaux
        3. Si mappings échouent et SLM dispo → utiliser SLM fallback
        4. Nettoyer les signaux de quarantaine si ville récupérée
        """
        if not party.country_town:
            return party
        
        from src.geonames.geonames_db import infer_city_from_postal_code
        from src.postal_slm_fallback import infer_city_via_slm_postal, needs_postal_slm_fallback
        
        t = party.country_town.town
        p = party.country_town.postal_code
        c = party.country_town.country
        
        # Récupérer postal code des fragments adresse si absent du country_town
        if not p and party.fragmented_addresses:
            for frag in party.fragmented_addresses:
                if frag.pst_cd:
                    p = frag.pst_cd
                    party.country_town.postal_code = p
                    break
        
        # Inférence postal → ville si conditions réunies
        if c and p and (not t or str(t).strip() in ["", "NONE", "N/A", "N A", "NULL"]):
            # Étape 1: Essayer le dictionnaire postal_mappings.json
            inferred_town = infer_city_from_postal_code(c, p)
            
            # Étape 2: Si échec du dictionnaire, essayer SLM fallback
            if not inferred_town and needs_postal_slm_fallback(c, p, t):
                try:
                    inferred_town = infer_city_via_slm_postal(c, p, model="phi3:mini")
                    if inferred_town:
                        if not party.meta.warnings:
                            party.meta.warnings = []
                        party.meta.warnings.append(f"geo_postal_inference_slm_{c}:{p}→{inferred_town}")
                except Exception as e:
                    logger.log("GEO", f"SLM postal fallback failed: {e}", level="WARN")
            elif inferred_town:
                # Dictionnaire réussit → ajouter warning standard
                if not party.meta.warnings:
                    party.meta.warnings = []
                party.meta.warnings.append(f"geo_postal_inference_{c}:{p}→{inferred_town}")
            
            # Appliquer l'inférence si trouvée
            if inferred_town:
                party.country_town.town = inferred_town
                t = inferred_town  # Mise à jour locale
        
        # 🧹 CLEANUP FINAL: Si la ville est désormais connue, nettoyer les signaux de quarantaine
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

    # POINT D: Audit Trail & "Human Verification Flag"
    # Lève un flag d'alerte métier pour aiguillage manuel si des doutes ou des avertissements persistent
    if e2.meta.warnings:
        critical_warnings = [
            "requires_manual_verification", 
            "pass1_town_ambiguous", 
            "pass1_country_missing"
        ]
        if any(cw in w for cw in critical_warnings for w in e2.meta.warnings):
            e2.meta.requires_manual_review = True
            
    # Autre cas de review manuel : L'IA a été appelée mais sa confiance globale est moyenne (< 0.8)
    if e2.meta.fallback_used and e2.meta.parse_confidence < 0.8:
        e2.meta.requires_manual_review = True

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
