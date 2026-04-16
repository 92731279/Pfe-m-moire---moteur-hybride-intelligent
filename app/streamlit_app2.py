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

from src.pipeline import run_pipeline
from src.pipeline_logger import PipelineLogger

# ─────────────────────────────────────────────
# CONFIG PAGE
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="SWIFT Engine · ISO 20022",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
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
    --accent-amber: #f59e0b;
    --accent-red:   #ef4444;
    --text-primary: #f1f5f9;
    --text-muted:   #64748b;
    --text-dim:     #334155;
    --mono:         'Space Mono', monospace;
    --sans:         'DM Sans', sans-serif;
}

/* ── Global reset ── */
html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg-base) !important;
    font-family: var(--sans) !important;
    color: var(--text-primary) !important;
}

[data-testid="stAppViewContainer"] {
    background:
        radial-gradient(ellipse 80% 40% at 10% -10%, rgba(37,99,235,0.12) 0%, transparent 60%),
        radial-gradient(ellipse 60% 40% at 90% 110%, rgba(6,182,212,0.08) 0%, transparent 60%),
        var(--bg-base) !important;
}

[data-testid="stHeader"] { background: transparent !important; }
[data-testid="stSidebar"] { background: var(--bg-card) !important; }

/* ── Main container ── */
.block-container {
    padding: 2rem 3rem !important;
    max-width: 1400px !important;
}

/* ── Hero header ── */
.hero-header {
    display: flex;
    align-items: center;
    gap: 1.5rem;
    padding: 2.5rem 2rem 2rem;
    margin-bottom: 2rem;
    border-bottom: 1px solid var(--border);
    position: relative;
}
.hero-header::after {
    content: '';
    position: absolute;
    bottom: -1px; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, var(--accent-blue), var(--accent-cyan), transparent);
}
.hero-logo {
    width: 52px; height: 52px;
    background: linear-gradient(135deg, #1d4ed8, #0891b2);
    border-radius: 14px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.6rem;
    box-shadow: 0 0 24px rgba(59,130,246,0.4);
}
.hero-title {
    font-family: var(--mono) !important;
    font-size: 1.5rem !important;
    font-weight: 700 !important;
    color: var(--text-primary) !important;
    letter-spacing: -0.02em;
    margin: 0 !important;
}
.hero-subtitle {
    font-size: 0.82rem;
    color: var(--text-muted);
    font-family: var(--mono);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-top: 0.2rem;
}
.hero-badge {
    margin-left: auto;
    padding: 0.3rem 0.9rem;
    border-radius: 999px;
    background: rgba(16,185,129,0.12);
    border: 1px solid rgba(16,185,129,0.3);
    color: var(--accent-green);
    font-size: 0.72rem;
    font-family: var(--mono);
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    animation: pulse-green 2s infinite;
}
@keyframes pulse-green {
    0%, 100% { box-shadow: 0 0 0 0 rgba(16,185,129,0.3); }
    50% { box-shadow: 0 0 0 6px rgba(16,185,129,0); }
}

/* ── Section labels ── */
.section-label {
    font-family: var(--mono);
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.15em;
    color: var(--accent-blue);
    margin-bottom: 0.6rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}
.section-label::before {
    content: '';
    display: inline-block;
    width: 16px; height: 2px;
    background: var(--accent-blue);
    border-radius: 1px;
}

/* ── Cards ── */
.card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    position: relative;
    overflow: hidden;
    transition: border-color 0.2s;
}
.card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(59,130,246,0.3), transparent);
}
.card:hover { border-color: rgba(59,130,246,0.4); }

/* ── Metric cards ── */
.metric-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 1rem;
    margin: 1.5rem 0;
}
.metric-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.2rem 1.4rem;
    position: relative;
    overflow: hidden;
    transition: all 0.2s;
}
.metric-card:hover {
    border-color: var(--border-glow);
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(37,99,235,0.15);
}
.metric-card .metric-icon {
    font-size: 1.4rem;
    margin-bottom: 0.6rem;
    display: block;
}
.metric-card .metric-label {
    font-size: 0.68rem;
    font-family: var(--mono);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--text-muted);
    margin-bottom: 0.3rem;
}
.metric-card .metric-value {
    font-family: var(--mono);
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--text-primary);
    line-height: 1;
}
.metric-card .metric-sub {
    font-size: 0.72rem;
    color: var(--text-muted);
    margin-top: 0.3rem;
}
.metric-card.green { border-color: rgba(16,185,129,0.25); }
.metric-card.green .metric-value { color: var(--accent-green); }
.metric-card.blue { border-color: rgba(59,130,246,0.25); }
.metric-card.blue .metric-value { color: var(--accent-blue); }
.metric-card.amber { border-color: rgba(245,158,11,0.25); }
.metric-card.amber .metric-value { color: var(--accent-amber); }
.metric-card.red { border-color: rgba(239,68,68,0.25); }
.metric-card.red .metric-value { color: var(--accent-red); }

/* ── Pipeline steps ── */
.pipeline-bar {
    display: flex;
    align-items: center;
    gap: 0;
    margin: 1.5rem 0;
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1rem 1.5rem;
    overflow-x: auto;
}
.pipe-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.3rem;
    min-width: 80px;
}
.pipe-step .step-dot {
    width: 36px; height: 36px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 0.9rem;
    font-weight: 700;
    font-family: var(--mono);
    border: 2px solid;
    transition: all 0.3s;
}
.pipe-step .step-name {
    font-size: 0.65rem;
    font-family: var(--mono);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--text-muted);
}
.pipe-step.done .step-dot {
    background: rgba(16,185,129,0.15);
    border-color: var(--accent-green);
    color: var(--accent-green);
}
.pipe-step.done .step-name { color: var(--accent-green); }
.pipe-step.active .step-dot {
    background: rgba(59,130,246,0.2);
    border-color: var(--accent-blue);
    color: var(--accent-blue);
    animation: pulse-blue 1s infinite;
}
.pipe-step.waiting .step-dot {
    background: transparent;
    border-color: var(--text-dim);
    color: var(--text-dim);
}
@keyframes pulse-blue {
    0%, 100% { box-shadow: 0 0 0 0 rgba(59,130,246,0.4); }
    50% { box-shadow: 0 0 0 8px rgba(59,130,246,0); }
}
.pipe-connector {
    flex: 1;
    height: 2px;
    min-width: 30px;
    background: var(--text-dim);
    position: relative;
    top: -14px;
}
.pipe-connector.done {
    background: linear-gradient(90deg, var(--accent-green), var(--accent-blue));
}

/* ── Log lines ── */
.log-container {
    background: #020817;
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1.2rem;
    font-family: var(--mono);
    font-size: 0.75rem;
    line-height: 1.8;
    max-height: 400px;
    overflow-y: auto;
}
.log-container::-webkit-scrollbar { width: 4px; }
.log-container::-webkit-scrollbar-track { background: transparent; }
.log-container::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }

.log-line { display: flex; gap: 0.8rem; align-items: flex-start; }
.log-ts { color: var(--text-dim); min-width: 65px; }
.log-step {
    min-width: 50px;
    padding: 0 6px;
    border-radius: 4px;
    font-size: 0.65rem;
    font-weight: 700;
    text-align: center;
}
.log-step.E0 { background: rgba(139,92,246,0.15); color: #a78bfa; }
.log-step.E1 { background: rgba(59,130,246,0.15); color: #60a5fa; }
.log-step.E2 { background: rgba(6,182,212,0.15); color: #22d3ee; }
.log-step.E3 { background: rgba(245,158,11,0.15); color: #fbbf24; }
.log-step.INPUT { background: rgba(100,116,139,0.15); color: #94a3b8; }
.log-step.OUTPUT { background: rgba(16,185,129,0.15); color: #34d399; }
.log-step.E2B { background: rgba(6,182,212,0.1); color: #67e8f9; }
.log-msg { color: var(--text-primary); flex: 1; }
.log-data { color: var(--text-muted); font-size: 0.68rem; }

/* ── Warning badges ── */
.warn-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.35rem 0.8rem;
    border-radius: 6px;
    font-size: 0.72rem;
    font-family: var(--mono);
    margin: 0.25rem 0.25rem 0.25rem 0;
    word-break: break-all;
}
.warn-badge.warn {
    background: rgba(245,158,11,0.1);
    border: 1px solid rgba(245,158,11,0.25);
    color: var(--accent-amber);
}
.warn-badge.info {
    background: rgba(59,130,246,0.1);
    border: 1px solid rgba(59,130,246,0.25);
    color: var(--accent-blue);
}
.warn-badge.ok {
    background: rgba(16,185,129,0.1);
    border: 1px solid rgba(16,185,129,0.25);
    color: var(--accent-green);
}
.warn-badge.err {
    background: rgba(239,68,68,0.1);
    border: 1px solid rgba(239,68,68,0.25);
    color: var(--accent-red);
}

/* ── Result banner ── */
.result-banner {
    padding: 1rem 1.5rem;
    border-radius: 10px;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    gap: 1rem;
    font-family: var(--mono);
    font-size: 0.82rem;
}
.result-banner.success {
    background: rgba(16,185,129,0.08);
    border: 1px solid rgba(16,185,129,0.3);
    color: var(--accent-green);
}
.result-banner.warning {
    background: rgba(245,158,11,0.08);
    border: 1px solid rgba(245,158,11,0.3);
    color: var(--accent-amber);
}
.result-banner.error {
    background: rgba(239,68,68,0.08);
    border: 1px solid rgba(239,68,68,0.3);
    color: var(--accent-red);
}

/* ── JSON viewer ── */
.stJson {
    background: #020817 !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    font-family: var(--mono) !important;
    font-size: 0.75rem !important;
}

/* ── Selectbox & inputs ── */
.stSelectbox > div > div,
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
    background: var(--bg-elevated) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    color: var(--text-primary) !important;
    font-family: var(--mono) !important;
    font-size: 0.82rem !important;
}
.stSelectbox > div > div:focus-within,
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
    border-color: var(--accent-blue) !important;
    box-shadow: 0 0 0 3px rgba(59,130,246,0.15) !important;
}

/* ── Labels ── */
.stSelectbox label, .stTextInput label, .stTextArea label {
    font-family: var(--mono) !important;
    font-size: 0.68rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.1em !important;
    color: var(--text-muted) !important;
    font-weight: 700 !important;
}

/* ── Button ── */
.stButton > button {
    background: linear-gradient(135deg, #1d4ed8, #0e7490) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.7rem 2rem !important;
    font-family: var(--mono) !important;
    font-size: 0.82rem !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    transition: all 0.2s !important;
    box-shadow: 0 4px 15px rgba(29,78,216,0.3) !important;
    width: 100% !important;
}
.stButton > button:hover {
    transform: translateY(-1px) !important;
    box-shadow: 0 8px 25px rgba(29,78,216,0.4) !important;
}
.stButton > button:active {
    transform: translateY(0) !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: var(--bg-card) !important;
    border-radius: 8px 8px 0 0 !important;
    border: 1px solid var(--border) !important;
    border-bottom: none !important;
    padding: 0.3rem !important;
    gap: 0.2rem !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: var(--text-muted) !important;
    font-family: var(--mono) !important;
    font-size: 0.72rem !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    border-radius: 6px !important;
    padding: 0.5rem 1rem !important;
    transition: all 0.2s !important;
}
.stTabs [aria-selected="true"] {
    background: rgba(59,130,246,0.15) !important;
    color: var(--accent-blue) !important;
}
.stTabs [data-baseweb="tab-panel"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border) !important;
    border-top: none !important;
    border-radius: 0 0 8px 8px !important;
    padding: 1.5rem !important;
}

/* ── Spinner ── */
.stSpinner > div { border-color: var(--accent-blue) transparent transparent !important; }

/* ── Address validation card ── */
.addr-card {
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 0.8rem;
}
.addr-card .addr-raw {
    font-family: var(--mono);
    font-size: 0.78rem;
    color: var(--accent-cyan);
    margin-bottom: 0.6rem;
    padding-bottom: 0.6rem;
    border-bottom: 1px solid var(--border);
}
.check-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.72rem;
    font-family: var(--mono);
    color: var(--text-muted);
    margin: 0.2rem 0;
}
.check-icon.ok { color: var(--accent-green); }
.check-icon.fail { color: var(--accent-red); }

/* ── Confidence bar ── */
.conf-bar-wrap {
    background: var(--bg-elevated);
    border-radius: 999px;
    height: 6px;
    margin-top: 0.5rem;
    overflow: hidden;
}
.conf-bar-fill {
    height: 100%;
    border-radius: 999px;
    transition: width 0.8s ease;
}

/* ── Divider ── */
hr { border-color: var(--border) !important; }

/* ── Hide Streamlit branding ── */
#MainMenu, footer, header { visibility: hidden; }
.viewerBadge_container__1QSob { display: none; }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
SAMPLES_PATH = Path(PROJECT_ROOT) / "data" / "samples" / "mt103_party_cases.json"


def load_sample_cases():
    if not SAMPLES_PATH.exists():
        return []
    with open(SAMPLES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def confidence_color(c: float) -> str:
    if c >= 0.85:
        return "green"
    if c >= 0.70:
        return "blue"
    if c >= 0.55:
        return "amber"
    return "red"


def confidence_bar_color(c: float) -> str:
    if c >= 0.85:
        return "linear-gradient(90deg, #10b981, #06b6d4)"
    if c >= 0.70:
        return "linear-gradient(90deg, #3b82f6, #06b6d4)"
    if c >= 0.55:
        return "linear-gradient(90deg, #f59e0b, #f97316)"
    return "linear-gradient(90deg, #ef4444, #f97316)"


def render_log_lines(events):
    lines_html = ""
    for e in events:
        step = e.get("step", "")
        ts = e.get("timestamp", "")
        msg = e.get("message", "")
        data = e.get("data", {})
        data_str = " · ".join(f"<span style='color:#3b82f6'>{k}</span>=<span style='color:#e2e8f0'>{v}</span>"
                              for k, v in data.items() if v)
        lines_html += f"""
        <div class="log-line">
            <span class="log-ts">{ts}</span>
            <span class="log-step {step}">{step}</span>
            <span class="log-msg">{msg}</span>
            <span class="log-data">{data_str}</span>
        </div>"""
    return f'<div class="log-container">{lines_html}</div>'


def render_warning_badges(warnings, signals=None):
    html = ""
    if not warnings and not signals:
        html += '<span class="warn-badge ok">✓ Aucun warning</span>'
    else:
        for w in (warnings or []):
            level = "warn"
            if "error" in w.lower() or "invalid" in w.lower() or "missing" in w.lower():
                level = "err"
            elif "validated" in w.lower() or "ok" in w.lower():
                level = "ok"
            icon = "⚠" if level == "warn" else ("✗" if level == "err" else "✓")
            html += f'<span class="warn-badge {level}">{icon} {w}</span>'
    for s in (signals or []):
        level = "err" if "error" in s.lower() else "info"
        icon = "⚡" if "slm" in s.lower() else "ℹ"
        html += f'<span class="warn-badge {level}">{icon} {s}</span>'
    return html


def render_address_validation(validations):
    if not validations:
        return "<p style='color:#64748b;font-family:monospace;font-size:0.8rem'>Aucune adresse à valider</p>"
    html = ""
    for v in validations:
        raw = v.get("raw", "")
        cv = v.get("contextual_valid", False)
        checks = v.get("contextual_checks", {})
        components = v.get("components", {})

        status_color = "#10b981" if cv else "#ef4444"
        status_text = "VALIDE" if cv else "INVALIDE"

        html += f"""
        <div class="addr-card">
            <div class="addr-raw">
                📍 {raw}
                <span style="float:right;color:{status_color};font-size:0.65rem;font-weight:700">
                    ● {status_text}
                </span>
            </div>"""

        for check_name, check_val in checks.items():
            if isinstance(check_val, bool):
                icon_class = "ok" if check_val else "fail"
                icon = "✓" if check_val else "✗"
                html += f"""
                <div class="check-row">
                    <span class="check-icon {icon_class}">{icon}</span>
                    {check_name.replace('_', ' ')}
                </div>"""

        if components:
            html += "<div style='margin-top:0.5rem;padding-top:0.5rem;border-top:1px solid #1e293b'>"
            for k, val in components.items():
                html += f"<span style='font-size:0.65rem;color:#475569;font-family:monospace;margin-right:0.5rem'><span style='color:#60a5fa'>{k}</span>: {val}</span>"
            html += "</div>"

        html += "</div>"
    return html

def render_fragmentation_results(frag_list):
    """Rend le résultat de la fragmentation pour l'interface"""
    if not frag_list:
        return "<p style='color:#64748b;font-family:monospace'>Aucune fragmentation (liste vide)</p>"
    
    html = ""
    for idx, frag in enumerate(frag_list):
        # Style pour fallback ou succès
        status_color = "var(--accent-green)" if not frag.fallback_used else "var(--accent-amber)"
        status_text = "Standard" if not frag.fallback_used else "Fallback AdrLine"
        
        html += f"""
        <div class='card' style="border-left: 4px solid {status_color}; margin-bottom: 15px;">
            <div style="display:flex; justify-content:space-between; margin-bottom:10px;">
                <span style="color:{status_color}; font-weight:bold; font-family:monospace;">
                    🧩 Fragmentation #{idx + 1} — {status_text}
                </span>
                <span style="color:#94a3b8; font-size:0.7rem;">Confiance: {frag.fragmentation_confidence:.0%}</span>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.85rem; color: var(--text-primary);">
                <div><small style="color:#64748b">StrtNm (Rue)</small><br><b>{frag.strt_nm or '—'}</b></div>
                <div><small style="color:#64748b">BldgNb (Numéro)</small><br><b>{frag.bldg_nb or '—'}</b></div>
                <div><small style="color:#64748b">Room (Unité)</small><br><b>{frag.room or '—'}</b></div>
                <div><small style="color:#64748b">PstCd (Code Postal)</small><br><b>{frag.pst_cd or '—'}</b></div>
                <div><small style="color:#64748b">TwnNm (Ville)</small><br><b>{frag.twn_nm or '—'}</b></div>
                <div><small style="color:#64748b">Ctry (Pays)</small><br><b>{frag.ctry or '—'}</b></div>
            </div>
            {f'<div style="margin-top:10px; padding-top:5px; border-top:1px dashed #334155;"><small style="color:#64748b">AdrLine (Fallback):</small> {frag.adr_line}</div>' if frag.fallback_used else ''}
        </div>
        """
    return html
# ─────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────
st.markdown("""
<div class="hero-header">
    <div class="hero-logo">⚡</div>
    <div>
        <div class="hero-title">SWIFT Hybrid Engine</div>
        <div class="hero-subtitle">E0 · E1 · E2 · E3 SLM &nbsp;|&nbsp; MT103 → ISO 20022 Canonical JSON</div>
    </div>
    <div class="hero-badge">● System Online</div>
</div>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────
sample_cases = load_sample_cases()
sample_labels = [case["label"] for case in sample_cases]

if "selected_sample_label" not in st.session_state:
    st.session_state.selected_sample_label = sample_labels[0] if sample_labels else "Saisie manuelle"
if "raw_message_input" not in st.session_state:
    st.session_state.raw_message_input = (
        sample_cases[0]["raw_message"] if sample_cases
        else ":50K:/FR7630006000011234567890189\nJANE DOE RUE DE LA REPUBLIQUE\nPARIS FRANCE\n"
    )

def _on_sample_change():
    selected = next(
        (case for case in sample_cases if case["label"] == st.session_state.selected_sample_label),
        None,
    )
    if selected:
        st.session_state.raw_message_input = selected["raw_message"]

# ─────────────────────────────────────────────
# INPUT PANEL
# ─────────────────────────────────────────────
col_input, col_config = st.columns([3, 1], gap="large")

with col_input:
    st.markdown('<div class="section-label">Message SWIFT</div>', unsafe_allow_html=True)

    if sample_cases:
        st.selectbox(
            "Dataset de cas de test",
            options=sample_labels,
            key="selected_sample_label",
            on_change=_on_sample_change,
        )

    raw_message = st.text_area(
        "Contenu brut",
        key="raw_message_input",
        height=200,
        placeholder=":50K:/FR76...\nNOM PRENOM\nRUE DE LA PAIX\nPARIS FRANCE",
    )

with col_config:
    st.markdown('<div class="section-label">Configuration</div>', unsafe_allow_html=True)
    message_id = st.text_input("Message ID", value="MSG_UI_001")
    slm_model = st.text_input("Modèle SLM", value="phi3:mini")

    st.markdown("<br>", unsafe_allow_html=True)
    run = st.button("⚡  Analyser le message", use_container_width=True)

    st.markdown("""
    <div style='margin-top:1rem;padding:0.8rem;background:rgba(30,58,95,0.3);
    border:1px solid rgba(37,99,235,0.2);border-radius:8px;'>
        <div style='font-family:monospace;font-size:0.65rem;color:#475569;
        text-transform:uppercase;letter-spacing:0.1em;margin-bottom:0.5rem'>
        Pipeline
        </div>
        <div style='font-family:monospace;font-size:0.7rem;color:#94a3b8;line-height:1.8'>
        E0 → Prétraitement<br>
        E1 → Parsing SWIFT<br>
        E2 → Validation 2-passes<br>
        E3 → SLM Fallback
        </div>
    </div>
    """, unsafe_allow_html=True)

# ─────────────────────────────────────────────
# PIPELINE EXECUTION
# ─────────────────────────────────────────────
if run:
    logger = PipelineLogger()

    # Pipeline progress bar
    progress_placeholder = st.empty()
    progress_placeholder.markdown("""
    <div class="pipeline-bar">
        <div class="pipe-step active">
            <div class="step-dot">E0</div>
            <div class="step-name">Prétraitement</div>
        </div>
        <div class="pipe-connector"></div>
        <div class="pipe-step waiting">
            <div class="step-dot">E1</div>
            <div class="step-name">Parsing</div>
        </div>
        <div class="pipe-connector"></div>
        <div class="pipe-step waiting">
            <div class="step-dot">E2</div>
            <div class="step-name">Validation</div>
        </div>
        <div class="pipe-connector"></div>
        <div class="pipe-step waiting">
            <div class="step-dot">E3</div>
            <div class="step-name">SLM</div>
        </div>
        <div class="pipe-connector"></div>
        <div class="pipe-step waiting">
            <div class="step-dot">✓</div>
            <div class="step-name">Output</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    try:
        start_time = time.time()

        with st.spinner("Exécution du pipeline en cours..."):
            result, logger = run_pipeline(
                raw_message=raw_message,
                message_id=message_id,
                slm_model=slm_model,
                logger=logger,
            )

        elapsed = round(time.time() - start_time, 2)
        slm_used = result.meta.fallback_used
        conf = result.meta.parse_confidence
        nb_warn = len(result.meta.warnings)

        # Pipeline done
        progress_placeholder.markdown("""
        <div class="pipeline-bar">
            <div class="pipe-step done"><div class="step-dot">E0</div><div class="step-name">Prétraitement</div></div>
            <div class="pipe-connector done"></div>
            <div class="pipe-step done"><div class="step-dot">E1</div><div class="step-name">Parsing</div></div>
            <div class="pipe-connector done"></div>
            <div class="pipe-step done"><div class="step-dot">E2</div><div class="step-name">Validation</div></div>
            <div class="pipe-connector done"></div>
            <div class="pipe-step done"><div class="step-dot">E3</div><div class="step-name">SLM</div></div>
            <div class="pipe-connector done"></div>
            <div class="pipe-step done"><div class="step-dot">✓</div><div class="step-name">Output</div></div>
        </div>
        """, unsafe_allow_html=True)

        # Result banner
        rejected = getattr(result.meta, "rejected", False)
        if rejected:
            st.markdown(f"""
            <div class="result-banner error">
                <span style="font-size:1.2rem">✗</span>
                <div>
                    <div style="font-weight:700">MESSAGE REJETÉ</div>
                    <div style="font-size:0.72rem;opacity:0.7;margin-top:0.2rem">
                        Éléments obligatoires manquants — correction requise avant traitement métier
                    </div>
                </div>
                <span style="margin-left:auto;opacity:0.6">{elapsed}s</span>
            </div>
            """, unsafe_allow_html=True)
        elif conf >= 0.75:
            st.markdown(f"""
            <div class="result-banner success">
                <span style="font-size:1.2rem">✓</span>
                <div>
                    <div style="font-weight:700">PIPELINE TERMINÉ — MESSAGE ACCEPTABLE</div>
                    <div style="font-size:0.72rem;opacity:0.7;margin-top:0.2rem">
                        Confiance {conf:.0%} · {nb_warn} warning(s) · SLM {'activé' if slm_used else 'non requis'}
                    </div>
                </div>
                <span style="margin-left:auto;opacity:0.6">{elapsed}s</span>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="result-banner warning">
                <span style="font-size:1.2rem">⚠</span>
                <div>
                    <div style="font-weight:700">PIPELINE TERMINÉ — CONFIANCE FAIBLE</div>
                    <div style="font-size:0.72rem;opacity:0.7;margin-top:0.2rem">
                        Confiance {conf:.0%} · {nb_warn} warning(s) · Vérification manuelle recommandée
                    </div>
                </div>
                <span style="margin-left:auto;opacity:0.6">{elapsed}s</span>
            </div>
            """, unsafe_allow_html=True)

        # ── Metrics ──
        cc = confidence_color(conf)
        bar_color = confidence_bar_color(conf)
        slm_color = "amber" if slm_used else "green"
        slm_val = "OUI" if slm_used else "NON"
        warn_color = "green" if nb_warn == 0 else ("amber" if nb_warn <= 3 else "red")

        st.markdown(f"""
        <div class="metric-grid">
            <div class="metric-card blue">
                <span class="metric-icon">🏷</span>
                <div class="metric-label">Field Type</div>
                <div class="metric-value">{result.field_type or "—"}</div>
                <div class="metric-sub">{result.role or ""}</div>
            </div>
            <div class="metric-card {cc}">
                <span class="metric-icon">📊</span>
                <div class="metric-label">Confiance</div>
                <div class="metric-value">{conf:.0%}</div>
                <div class="conf-bar-wrap">
                    <div class="conf-bar-fill" style="width:{conf*100:.0f}%;background:{bar_color}"></div>
                </div>
            </div>
            <div class="metric-card {slm_color}">
                <span class="metric-icon">🤖</span>
                <div class="metric-label">Fallback SLM</div>
                <div class="metric-value">{slm_val}</div>
                <div class="metric-sub">{slm_model}</div>
            </div>
            <div class="metric-card {warn_color}">
                <span class="metric-icon">⚡</span>
                <div class="metric-label">Warnings</div>
                <div class="metric-value">{nb_warn}</div>
                <div class="metric-sub">détectés</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Tabs ──
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "⬡  JSON Canonique",
            "⬡  Logs Pipeline",
            "⬡  Warnings & Signaux",
            "⬡  Validation Adresse",
            "⬡  Fragmentation ISO"  # ✅ NOUVEAU
        ])

        with tab1:
            st.markdown('<div class="section-label">Résultat JSON ISO 20022</div>',
                        unsafe_allow_html=True)
            st.json(result.model_dump())

        with tab2:
            st.markdown('<div class="section-label">Logs détaillés</div>',
                        unsafe_allow_html=True)
            events = logger.as_dicts()
            st.markdown(render_log_lines(events), unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)
            st.markdown('<div class="section-label">Logs structurés</div>',
                        unsafe_allow_html=True)
            st.json(events)

        with tab3:
            col_w, col_s = st.columns(2, gap="medium")
            with col_w:
                st.markdown('<div class="section-label">Warnings métier</div>',
                            unsafe_allow_html=True)
                st.markdown(
                    render_warning_badges(result.meta.warnings),
                    unsafe_allow_html=True,
                )
            with col_s:
                st.markdown('<div class="section-label">Signaux SLM</div>',
                            unsafe_allow_html=True)
                st.markdown(
                    render_warning_badges([], result.meta.llm_signals),
                    unsafe_allow_html=True,
                )

        with tab4:
            st.markdown('<div class="section-label">Validation adresse — Pass 2</div>',
                        unsafe_allow_html=True)
            st.markdown(
                render_address_validation(result.address_validation or []),
                unsafe_allow_html=True,
            )

        with tab5:
            st.markdown('<div class="section-label">Résultat de la Fragmentation (E2.5)</div>', unsafe_allow_html=True)
            # On suppose que 'result' est ton objet CanonicalParty
            if hasattr(result, 'fragmented_addresses') and result.fragmented_addresses:
                st.markdown(render_fragmentation_results(result.fragmented_addresses), unsafe_allow_html=True)
            else:
                st.info("Aucune adresse à fragmenter pour ce message.")
        
   
    except Exception as e:
        import traceback
        progress_placeholder.empty()
        st.markdown(f"""
        <div class="result-banner error">
            <span style="font-size:1.2rem">✗</span>
            <div>
                <div style="font-weight:700">ERREUR PIPELINE</div>
                <div style="font-family:monospace;font-size:0.75rem;opacity:0.8;margin-top:0.3rem">
                    {type(e).__name__}: {str(e)[:200]}
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        with st.expander("Traceback complet"):
            st.code(traceback.format_exc(), language="python")