"""streamlit_app.py — Interface Streamlit moderne du moteur hybride SWIFT"""

import os
import sys
import json
import streamlit as st
import time
from pathlib import Path

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# FORCE_RELOAD_TRIGGER_3
import sys
for m in list(sys.modules.keys()):
    if m.startswith("src."):
        del sys.modules[m]

from src.pipeline import run_pipeline
from src.pipeline_logger import PipelineLogger
from src.iso20022_mapper import build_iso20022_party_xml
from src.quality_metrics import compute_reliability_score

# ─────────────────────────────────────────────
# CONFIG PAGE
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="SWIFT Engine · ISO 20022",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# CUSTOM CSS — Dark Fintech Theme
# ─────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600;700&display=swap');

/* ── Root variables ── */
:root {
    --bg-base:      #090e1a;
    --bg-card:      #0f172a;
    --bg-elevated:  #1e293b;
    --border:       #1e3a5f;
    --border-glow:  #2563eb;
    --accent-blue:  #3b82f6;
    --accent-cyan:  #06b6d4;
    --accent-green: #10b981;
    --text-primary: #f1f5f9;
    --text-muted:   #64748b;
    --mono:         'Space Mono', monospace;
    --sans:         'DM Sans', sans-serif;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg-base) !important;
    font-family: var(--sans) !important;
    color: var(--text-primary) !important;
}

.hero-header {
    display: flex; align-items: center; gap: 1.5rem;
    padding: 2rem; margin-bottom: 2rem;
    border-bottom: 1px solid var(--border);
    position: relative;
}
.hero-title {
    font-family: var(--mono) !important; font-size: 1.5rem !important; font-weight: 700 !important; color: var(--text-primary) !important; margin: 0 !important;
}
.hero-subtitle { font-size: 0.82rem; color: var(--text-muted); font-family: var(--mono); text-transform: uppercase; margin-top: 0.2rem; }

.live-trace-box {
    background: #0f172a;
    border-left: 4px solid #3b82f6;
    padding: 1rem;
    font-family: var(--mono);
    font-size: 0.85rem;
    color: #94a3b8;
    height: 300px;
    overflow-y: auto;
    border-radius: 0 8px 8px 0;
    margin-bottom: 1rem;
}
.trace-step { color: #f59e0b; font-weight: bold; }
.trace-success { color: #10b981; }
.trace-fail { color: #ef4444; }
.trace-slm { color: #a855f7; font-weight: bold;}

.result-card {
    background: #1e293b; padding: 1.5rem; border-radius: 12px;
    border: 1px solid rgba(59,130,246,0.3); margin-top: 1rem;
}
.result-field { font-family: var(--mono); font-size: 0.9rem; margin-bottom: 0.5rem; }
.result-label { color: #06b6d4; font-weight: bold; width: 120px; display: inline-block; }

.stButton > button {
    background: linear-gradient(135deg, #1d4ed8, #0e7490) !important;
    color: white !important; font-weight: bold !important;
    width: 100% !important; border: none !important;
}

#MainMenu, footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# LIVE LOGGER CLASS
# ─────────────────────────────────────────────
class StreamlitLiveLogger(PipelineLogger):
    def __init__(self, trace_container):
        super().__init__()
        self.trace_container = trace_container
        self.trace_html = ""
        self.step_colors = {
            "INPUT": "trace-step", "E0": "trace-step", "E1": "trace-success",
            "E2": "trace-success", "E2.5": "trace-step", "E3": "trace-slm",
            "E2B": "trace-step", "E2.5B": "trace-step", "DECISION": "trace-fail", "OUTPUT": "trace-success"
        }

    def log(self, step: str, message: str, level: str = "INFO", **data):
        super().log(step, message, level, **data)
        
        # Color styling
        color_class = self.step_colors.get(step, "")
        if "rejeté" in message.lower() or "erreur" in message.lower(): color_class = "trace-fail"
        if "Terminé" in message or "terminée" in message: color_class = "trace-success"
        if "SLM" in step: color_class = "trace-slm"

        details = ""
        if data:
            details = " <span style='opacity:0.6;font-size:0.75rem'>[" + ", ".join(f"{k}={v}" for k, v in data.items()) + "]</span>"
            
        line_html = f"<div style='margin-bottom:4px'><b>[{step}]</b> <span class='{color_class}'>{message}</span>{details}</div>"
        self.trace_html += line_html
        
        # Mettre à jour l'affichage en temps réel
        self.trace_container.markdown(
            f"<div class='live-trace-box'>{self.trace_html}</div>", 
            unsafe_allow_html=True
        )

# ─────────────────────────────────────────────
# DATA LOAD
# ─────────────────────────────────────────────
SAMPLES_PATH = Path(PROJECT_ROOT) / "data" / "samples" / "mt103_party_cases.json"

def load_cases():
    base_cases = []
    if SAMPLES_PATH.exists():
        with open(SAMPLES_PATH, "r", encoding="utf-8") as f:
            base_cases = json.load(f)
    
    # NOUVEAUX CAS EXTRÊMES AJOUTÉS POUR LA SOUTENANCE
    extreme_cases = [
        {
            "label": "🔥 EXTRÊME - Sans retour chariot (Chaos Total)",
            "raw_message": ":59:/123456 MONSIEUR BOURGUIBA HABIB RUE DE LA LIBERTE APPT 4B 8000 NABEUL TUNISIE",
            "category": "extreme"
        },
        {
            "label": "🔥 EXTRÊME - Ordre inversé + Info Bruitée",
            "raw_message": ":50K:/TN4839\n2037 ARIANA\nZ.I. CHOTRANA 2\nSOCIETE MEUBLATEX SA\nATTN DIR FINANCIER",
            "category": "extreme"
        },
        {
            "label": "🔥 EXTRÊME - Dédution Ville via Code Postal 1000",
            "raw_message": ":59:/TN123\nAHMED TRABELSI\nAVENUE DE PARIS 1000\nTUNISIE",
            "category": "extreme"
        }
    ]
    return extreme_cases + base_cases

cases = load_cases()
options = {f"{c['label']}": c["raw_message"] for c in cases}

# ─────────────────────────────────────────────
# NAVIGATION & ROUTING
# ─────────────────────────────────────────────
st.sidebar.title("Navigation PFE")
page = st.sidebar.radio(
    "📌 Choisissez le mode :",
    ["Mode Avancé (Démo Initiale)", "Mode Démo Simple (Validation)", "Architecture & Méthodologie"]
)

if page == "Mode Avancé (Démo Initiale)":
    # UI LAYOUT
    # ─────────────────────────────────────────────
    st.markdown("""
    <div class="hero-header">
        <div class="hero-logo">⚡</div>
        <div>
            <h1 class="hero-title">Moteur Hybride Intelligent</h1>
            <div class="hero-subtitle">Heuristique + SLM Local (Ollama Qwen2.5:0.5b) + GeoNames</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1.4], gap="large")

    with col1:
        st.markdown("### 📥 Entrée SWIFT")
        dataset_choice = st.selectbox("Sélectionner un cas de test", options=list(options.keys()))
        
        if dataset_choice:
            default_val = options[dataset_choice]
        else:
            default_val = ":59:/TN123456\nNOM PRENOM\nADRESSE\nVILLE PAYS"

        raw_message = st.text_area("Message SWIFT Brut", value=default_val, height=180)
        
        slm_model = st.text_input("Générateur IA (Fallback)", value="qwen2.5:0.5b", disabled=True)
        
        run = st.button("🚀 LANCER L'ANALYSE EN TEMPS RÉEL")

    with col2:
        st.markdown("### ⏱️ Traçabilité Intelligente (Temps Réel)")
        trace_container = st.empty()
        trace_container.markdown("<div class='live-trace-box'>En attente du lancement...</div>", unsafe_allow_html=True)
        
        result_container = st.empty()

    if run:
        with st.spinner("Analyse du moteur hybride en cours... (Patientez, l'IA peut prendre ~10 sec si appelée)"):
            start_time = time.time()
            
            # Le logger mettra à jour 'trace_container' en direct !
            live_logger = StreamlitLiveLogger(trace_container)
            
            # Exécution du vrai pipeline
            result, _ = run_pipeline(
                raw_message=raw_message,
                message_id="UI_TEST",
                slm_model="qwen2.5:0.5b",
                logger=live_logger
            )
            reliability = compute_reliability_score(result)
            
            elapsed = round(time.time() - start_time, 2)
            
            # --- Alerte / Popup Visuel (Demandée en Réunion) ---
            if getattr(result.meta, 'rejected', False):
                st.toast("🚨 MESSAGE REJETÉ : L'entrée nécessite une intervention !", icon="🚨")
                st.error("❌ **MESSAGE REJETÉ** : L'adresse est trop ambiguë ou incomplète. **Une modification manuelle de l'input est requise.**", icon="❌")
                status_header = "❌ Résultat Rejeté (À corriger)"
                header_color = "#ef4444"
            else:
                st.toast("✅ MESSAGE ACCEPTÉ : L'analyse a réussi !", icon="✅")
                st.success("✅ **MESSAGE ACCEPTÉ** : L'adresse a été extraite et validée avec succès.", icon="✅")
                status_header = "✅ Résultat Accepté"
                header_color = "#10b981"

            # Affichage du résultat principal
            res_html = f"""
            <div class="result-card" style="border-left: 5px solid {header_color};">
                <h4 style="margin-top:0; color: {header_color};">{status_header} ({elapsed}s)</h4>
                <div class="result-field"><span class="result-label">Nom :</span> {result.name or '-'}</div>
                <div class="result-field"><span class="result-label">Adresse :</span> {' '.join(result.address_lines) if result.address_lines else '-'}</div>
                <div class="result-field"><span class="result-label">Ville :</span> {result.country_town.town if result.country_town and result.country_town.town else '-'} <span style="font-size:0.7rem; color: #10b981;">(Auto-Déduite ✅)</span></div>
                <div class="result-field"><span class="result-label">Code Postal :</span> {result.country_town.postal_code if result.country_town and result.country_town.postal_code else '-'}</div>
                <div class="result-field"><span class="result-label">Pays (ISO) :</span> {result.country_town.country if result.country_town and result.country_town.country else '-'}</div>
                <hr>
                <div class="result-field"><span class="result-label">Voie utilisée :</span> {"🧠 IA Générative (Fallback)" if getattr(result.meta, 'fallback_used', False) else "⚙️ Algorithmique (Heuristique)"}</div>
                <div class="result-field"><span class="result-label">Confiance :</span> {int((result.meta.parse_confidence or 0)*100)}%</div>
                <div class="result-field"><span class="result-label">Fiabilité Pipeline :</span> {reliability['percent']}% ({reliability['band']})</div>
            </div>
            """
            result_container.markdown(res_html, unsafe_allow_html=True)
            iso_xml, iso_payload, iso_errors = build_iso20022_party_xml(result, include_envelope=True)
            
            # Onglets Détails Cachés
            st.markdown("### 🗂️ Détails Techniques de l'Objet")
            t1, t2, t3, t4, t5 = st.tabs([
                "🗃️ Analyse JSON Complet",
                "⚠️ Signaux & Warnings",
                "✂️ Fragmentation d'Adresse",
                "🧩 JSON ISO 20022",
                "🧾 XML ISO 20022",
            ])
            
            with t1:
                try:
                    st.json(result.model_dump())
                except:
                    import dataclasses
                    st.json(dataclasses.asdict(result) if dataclasses.is_dataclass(result) else vars(result))
                    
            with t2:
                st.write(f"**Confiance Parse :** {result.meta.parse_confidence}")
                st.write(f"**Fiabilité Pipeline :** {reliability['score']} ({reliability['band']})")
                st.write("**Composants fiabilité :**", reliability["components"])
                st.write("**Justifications :**", reliability["reasons"])
                st.write(f"**Message Rejeté :** {result.meta.rejected}")
                st.write("**Raisons de Rejet :**", result.meta.rejection_reasons)
                st.write("**Warnings Générés :**", result.meta.warnings)
                st.write("**Signaux du SLM :**", result.meta.llm_signals)
                
            with t3:
                frag_list = getattr(result, 'fragmented_addresses', [])
                if not frag_list:
                    st.info("Aucune fragmentation générée pour ce message.")
                else:
                    for idx, f in enumerate(frag_list):
                        st.write(f"**Passe {idx+1} (Confiance : {f.fragmentation_confidence}) :**")
                        try:
                            st.json(f.model_dump())
                        except:
                            st.json(dataclasses.asdict(f) if dataclasses.is_dataclass(f) else vars(f))

            with t4:
                st.json(iso_payload)

            with t5:
                if iso_errors:
                    st.warning("Validation locale ISO incomplète: " + " | ".join(iso_errors))
                else:
                    st.success("Structure ISO 20022 prête et XML bien formé.")
                st.code(iso_xml, language="xml")


elif page == "Mode Démo Simple (Validation)":
    st.markdown("""
    <div class=\"hero-header\">
        <div class=\"hero-logo\">✅</div>
        <div>
            <h1 class=\"hero-title\">Mode Démo Simple (Validation)</h1>
            <div class=\"hero-subtitle\">Tests simples pour la soutenance</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1], gap="large")
    with col1:
        st.markdown("### 📥 Saisie du SWIFT MT103")
        dataset_choice = st.selectbox("Sélectionner un cas de test (Démo)", options=list(options.keys()))
        default_val = options[dataset_choice] if dataset_choice else ":59:/TN123456\nNOM PRENOM\nADRESSE\nVILLE PAYS"
        raw_message = st.text_area("Message SWIFT Brut", value=default_val, height=200)
        run_simple = st.button("▶️ EXTRAIRE LE JSON")

    with col2:
        st.markdown("### 📤 Données Extraites")
        if run_simple:
            class SilentLogger:
                def log(self, *args, **kwargs): pass
            with st.spinner("Extraction en cours..."):
                result, _ = run_pipeline(raw_message=raw_message, message_id="DEMO", logger=SilentLogger())
                reliability = compute_reliability_score(result)
                iso_xml, iso_payload, iso_errors = build_iso20022_party_xml(result, include_envelope=True)
                # Construct clean dictionary
                clean_json = {
                    "ACCOUNT": result.account,
                }
                if result.party_id:
                    clean_json["PARTY_ID"] = getattr(result.party_id, "identifier", str(result.party_id))
                
                clean_json.update({
                    "NAME": result.name,
                    "ADDRESS_LINES": result.address_lines,
                    "COUNTRY": result.country_town.country if result.country_town else None,
                    "TOWN_NAME": result.country_town.town if result.country_town else None,
                    "POSTAL_CODE": result.country_town.postal_code if result.country_town else None,
                    "POSTAL_COMPLEMENT": getattr(result, "postal_complement", None),
                    "NATIONAL_ID": result.national_id,
                })
                
                if result.dob:
                    if result.dob.year and result.dob.month and result.dob.day:
                        clean_json["DOB"] = f"{result.dob.year}-{result.dob.month}-{result.dob.day}"
                    elif getattr(result.dob, "raw", None):
                        raw_date = result.dob.raw
                        if len(raw_date) == 8 and raw_date.isdigit():
                            clean_json["DOB"] = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:]}"
                        else:
                            clean_json["DOB"] = raw_date
                if result.pob and getattr(result.pob, "city", None):
                    clean_json["POB_CITY"] = result.pob.city
                if result.org_id:
                    clean_json["ORG_ID"] = getattr(result.org_id, "identifier", str(result.org_id))
                
                # Remove None values for a cleaner display
                clean_json = {k: v for k, v in clean_json.items() if v}

                # Add fragmented fields if any, avoiding raw and booleans/meta/warnings
                if result.fragmented_addresses:
                    # Use highest confidence fragment if multiple exist
                    best_frag = sorted(result.fragmented_addresses, key=lambda f: getattr(f, 'fragmentation_confidence', 0.0), reverse=True)[0]
                    for key, val in best_frag.model_dump().items():
                        if val and key not in ['fragmentation_confidence', 'raw_address', 'parser_type'] and not isinstance(val, bool) and not isinstance(val, list):
                            if key.upper() not in clean_json:
                                clean_json[key.upper()] = val
                
                if getattr(result.meta, 'rejected', False):
                    st.toast("🚨 MESSAGE REJETÉ", icon="🚨")
                    st.error("❌ **MESSAGE REJETÉ** : Veuillez modifier l'entrée SWIFT.", icon="❌")
                else:
                    st.toast("✅ MESSAGE ACCEPTÉ", icon="✅")
                    st.success(f"✅ Extraction Terminée avec {int((result.meta.parse_confidence or 0)*100)}% de confiance")

                st.info(f"Fiabilité pipeline estimée: {reliability['percent']}% ({reliability['band']})")
                    
                st.json(clean_json)
                st.markdown("### 🧩 Mapping ISO 20022")
                st.json(iso_payload)
                st.markdown("### 🧾 XML ISO 20022")
                if iso_errors:
                    st.warning("Validation locale ISO incomplète: " + " | ".join(iso_errors))
                else:
                    st.success("XML ISO 20022 généré avec succès.")
                st.code(iso_xml, language="xml")

elif page == "Architecture & Méthodologie":
    st.markdown("""
    <div class=\"hero-header\">
        <div class=\"hero-logo\">💡</div>
        <div>
            <h1 class=\"hero-title\">Architecture & Méthodologie TDD</h1>
            <div class=\"hero-subtitle\">Conception du Moteur Hybride SWIFT</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    ### 1. Méthodologie de Travail (TDD & Empirique)
    - **Test-Driven Development (Piloté par les tests) :** Toute correction des règles (Regex, dictionnaire, Libpostal) n'a été implémentée qu'après l'ajout d'un test automatisé dans `Pytest` qui vérifie l'absence de régression. 
    - **Approche Data-Driven (Empirique) :** L'algorithmique a été construite couche par couche en profilant les erreurs de transcription directement depuis les messages MT103 réels extraits.

    ### 2. Flux de Traitement (Pipeline Hybride)
    """)
    st.code("""
           [Message SWIFT MT103 Ligne: 59 / 50K]
                        ↓
           ==== MOTEUR DE CORRECTION ====
                        ↓
         (E1) Parseur Regex Déterministe (Dictionnaires)
         (E2) Validation GeoNames Locale (SQLite)
         (E2.5) C-Core Libpostal Fragmentation
                        ↓
        [Confiance Globale est-elle > 75%] —> OUI —> 🟢 OUTPUT (Fiable)
                        ↓
                       NON (Ambigu)
                        ↓
         (E3) SLM Rescue Prompting (Réseau de Secours)
                        ↓
               ==== SORTIE JSON =====
          (Composants conformes ISO 20022)
    """, language='markdown')

    st.markdown("""
    ### 3. Stack Technique Sécurisée
    - **Langage & Core :** Python 3.12 🐍, Dataclasses strictes (Pydantic), Pytest (CI/CD) 📋
    - **Base de connaissances Géographique :** API Locale _GeoNames_ via base relationnelle (SQLite) 🌍
    - **Traitement du Langage Naturel (NLP) :** _Libpostal_ pour la compréhension sémantique des adresses 🏢
    - **Small Language Model (IA) :** _Ollama_ exécutant le modèle **Qwen 2.5:0.5b** **100% en local** 🚫☁️ garantissant Zéro fuite de données bancaires sensibles.
    - **Interface UX :** _Streamlit_ pour le portail d'audit et la visibilité en temps réel 📊
    """)
