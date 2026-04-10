"""pipeline.py — Orchestration complète du moteur hybride SWIFT"""

from src.e0_preprocess import preprocess
from src.e1_parser import parse_field
from src.e2_validator import validate_party_semantics
from src.e3_slm_fallback import needs_slm_fallback, apply_slm_fallback
from src.pipeline_logger import PipelineLogger


def run_pipeline(
    raw_message: str,
    message_id: str = "MSG_PIPELINE",
    slm_model: str = "phi3:mini",
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
        logger.log(
            "E2B", "Revalidation terminée",
            confidence=e2.meta.parse_confidence,
            warnings=e2.meta.warnings,
        )

    logger.log("OUTPUT", "Pipeline terminé")
    return e2, logger
