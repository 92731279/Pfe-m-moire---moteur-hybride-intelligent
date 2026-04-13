"""streamlit_app.py — Interface Streamlit du moteur hybride SWIFT"""

import os
import sys
import json
import streamlit as st
import time
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.pipeline import run_pipeline
from src.pipeline_logger import PipelineLogger

st.set_page_config(page_title="Moteur hybride SWIFT", layout="wide")

st.title("Moteur hybride SWIFT → JSON canonique")
st.caption("E0 Prétraitement · E1 Parsing · E2 Validation · E3 SLM")

SAMPLES_PATH = Path(PROJECT_ROOT) / "data" / "samples" / "mt103_party_cases.json"


def load_sample_cases():
    if not SAMPLES_PATH.exists():
        return []
    with open(SAMPLES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


sample_cases = load_sample_cases()
sample_labels = [case["label"] for case in sample_cases]

if not sample_cases:
    default_message = """:50K:/FR7630006000011234567890189
JANE DOE RUE DE LA REPUBLIQUE
PARIS FRANCE
"""
else:
    default_message = sample_cases[0]["raw_message"]

if "selected_sample_label" not in st.session_state:
    st.session_state.selected_sample_label = sample_labels[0] if sample_labels else "Saisie manuelle"

if "raw_message_input" not in st.session_state:
    st.session_state.raw_message_input = default_message


def _on_sample_change():
    selected = next(
        (case for case in sample_cases if case["label"] == st.session_state.selected_sample_label),
        None,
    )
    if selected:
        st.session_state.raw_message_input = selected["raw_message"]


if sample_cases:
    st.selectbox(
        "Cas de test dataset",
        options=sample_labels,
        key="selected_sample_label",
        on_change=_on_sample_change,
    )

raw_message = st.text_area("Message SWIFT brut", key="raw_message_input", height=220)
message_id = st.text_input("Message ID", value="MSG_UI_001")
slm_model = st.text_input("Modèle SLM", value="phi3:mini")

run = st.button("Lancer le pipeline")

if run:
    logger = PipelineLogger()
    status_box = st.empty()
    info_box = st.empty()

    try:
        start_time = time.time()
        status_box.info("Pipeline en cours d'exécution...")
        with st.spinner("Analyse du message SWIFT, parsing, validation et fallback SLM..."):
            result, logger = run_pipeline(
                raw_message=raw_message,
                message_id=message_id,
                slm_model=slm_model,
                logger=logger,
            )

        elapsed = round(time.time() - start_time, 2)
        status_box.success(f"Pipeline terminé avec succès en {elapsed} s")
        info_box.caption("Résultat prêt. Consulte les onglets ci-dessous.")

        if result.meta.rejected:
            st.error(
                "Message rejete : elements obligatoires manquants. "
                "Le message doit etre corrige en entree avant traitement."
            )
            if result.meta.rejection_reasons:
                for reason in result.meta.rejection_reasons:
                    st.warning(reason)
        else:
            st.success("Message acceptable pour traitement metier.")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Field type", result.field_type or "-")
        c2.metric("Confiance", result.meta.parse_confidence)
        c3.metric("Fallback SLM", "Oui" if result.meta.fallback_used else "Non")
        c4.metric("Nb warnings", len(result.meta.warnings))

        tab1, tab2, tab3, tab4 = st.tabs(["JSON final", "Logs pipeline", "Warnings", "Validation adresse"])

        with tab1:
            st.subheader("JSON canonique")
            st.json(result.model_dump())

        with tab2:
            st.subheader("Logs détaillés")
            st.code(logger.format_console(), language="text")
            st.subheader("Logs structurés")
            st.json(logger.as_dicts())

        with tab3:
            st.subheader("Warnings")
            if result.meta.warnings:
                for w in result.meta.warnings:
                    st.warning(w)
            else:
                st.success("Aucun warning")
            st.subheader("Signals SLM")
            if result.meta.llm_signals:
                for s in result.meta.llm_signals:
                    st.info(s)
            else:
                st.success("Aucun signal SLM")

        with tab4:
            st.subheader("Validation d'adresse")
            if result.address_validation:
                st.json(result.address_validation)
            else:
                st.info("Aucune validation d'adresse disponible")

    except Exception as e:
        st.error(f"Erreur pipeline : {type(e).__name__}: {e}")
