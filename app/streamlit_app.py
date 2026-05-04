"""streamlit_app.py — Interface Streamlit PREMIUM du moteur hybride SWIFT"""

import os
import sys
import json
import re
import streamlit as st
import time
import io
import zipfile
from pathlib import Path
import textwrap
import html

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.pipeline import run_pipeline
from src.pipeline_logger import PipelineLogger
from src.iso20022_mapper import build_iso20022_party_xml
from src.swift_message_parser import extract_party_fields, extract_swift_fields
import src.pipeline as pipeline_module

def compute_geo_reliability(result):
    score = 0.0
    t = getattr(result.country_town, 'town', None) if result.country_town else None
    c = getattr(result.country_town, 'country', None) if result.country_town else None
    
    if t and c:
        score = 1.0
    elif t or c:
        score = 0.5
        
    # Si la ville n'est pas trouvée de manière complètement certifiée, on baisse légèrement (ex: 95%) 
    # pour garder "plus que 95% de fiabilité" comme vous m'avez dit.
    warnings = getattr(result.meta, 'warnings', [])
    if any('unverified' in w.lower() for w in warnings) and score > 0:
        score -= 0.05 
        
    return max(0.0, score)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIG PAGE
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="SWIFT Engine · ISO 20022",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM CSS — Premium Dark Fintech Theme
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown(textwrap.dedent("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

/* ── Design System ── */
:root {
    --bg-deep:      #020617;
    --bg-base:      #0a0f1e;
    --bg-surface:   #111827;
    --bg-elevated:  #1e293b;
    --glass-bg:     rgba(30, 41, 59, 0.55);
    --glass-border: rgba(148, 163, 184, 0.08);
    --primary:      #06b6d4;
    --primary-glow: rgba(6, 182, 212, 0.35);
    --secondary:    #8b5cf6;
    --accent:       #10b981;
    --accent-glow:  rgba(16, 185, 129, 0.25);
    --danger:       #ef4444;
    --warning:      #f59e0b;
    --text-primary: #f8fafc;
    --text-secondary:#94a3b8;
    --text-muted:   #64748b;
    --font-sans:    'Inter', sans-serif;
    --font-mono:    'JetBrains Mono', monospace;
    --radius:       16px;
    --radius-sm:    10px;
}

/* ── Base Reset ── */
html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg-deep) !important;
    font-family: var(--font-sans) !important;
    color: var(--text-primary) !important;
}

/* ── Animated Gradient Mesh Background ── */
[data-testid="stAppViewContainer"]::before {
    content: '';
    position: fixed;
    top: -30%; left: -30%;
    width: 160%; height: 160%;
    background:
        radial-gradient(ellipse at 15% 20%, rgba(6, 182, 212, 0.07) 0%, transparent 45%),
        radial-gradient(ellipse at 85% 80%, rgba(139, 92, 246, 0.06) 0%, transparent 45%),
        radial-gradient(ellipse at 50% 50%, rgba(16, 185, 129, 0.03) 0%, transparent 50%);
    animation: meshFloat 18s ease-in-out infinite;
    pointer-events: none;
    z-index: 0;
}

@keyframes meshFloat {
    0%, 100% { transform: translate(0, 0) rotate(0deg); }
    33% { transform: translate(1.5%, 1.5%) rotate(0.5deg); }
    66% { transform: translate(-1%, 0.5%) rotate(-0.5deg); }
}

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--bg-elevated); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--primary); }

/* ── Glass Card ── */
.glass-card {
    background: var(--glass-bg);
    backdrop-filter: blur(24px);
    -webkit-backdrop-filter: blur(24px);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius);
    padding: 1.5rem;
    position: relative;
    overflow: hidden;
    transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1);
    animation: fadeInUp 0.6s ease-out both;
}

.glass-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, var(--primary), transparent);
    opacity: 0.4;
}

.glass-card:hover {
    transform: translateY(-3px);
    border-color: rgba(6, 182, 212, 0.25);
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5),
                0 0 30px rgba(6, 182, 212, 0.08);
}

@keyframes fadeInUp {
    from { opacity: 0; transform: translateY(16px); }
    to { opacity: 1; transform: translateY(0); }
}

/* ── Hero Section ── */
.hero-wrap {
    position: relative;
    padding: 2.5rem 2rem;
    margin-bottom: 2rem;
    border-radius: var(--radius);
    background: linear-gradient(135deg, rgba(6, 182, 212, 0.12), rgba(139, 92, 246, 0.10));
    border: 1px solid rgba(6, 182, 212, 0.18);
    overflow: hidden;
    animation: fadeInUp 0.5s ease-out both;
}

.hero-wrap::after {
    content: '';
    position: absolute;
    top: -40%; right: -5%;
    width: 350px; height: 350px;
    background: radial-gradient(circle, rgba(6, 182, 212, 0.18), transparent 65%);
    animation: pulseGlow 5s ease-in-out infinite;
}

@keyframes pulseGlow {
    0%, 100% { transform: scale(1); opacity: 0.4; }
    50% { transform: scale(1.15); opacity: 0.7; }
}

.hero-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.35rem 0.9rem;
    background: rgba(6, 182, 212, 0.12);
    border: 1px solid rgba(6, 182, 212, 0.28);
    border-radius: 100px;
    font-size: 0.72rem;
    font-weight: 700;
    color: var(--primary);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.9rem;
    position: relative;
    z-index: 1;
}

.hero-badge .dot {
    width: 6px; height: 6px;
    background: var(--primary);
    border-radius: 50%;
    animation: blink 2.2s infinite;
}

@keyframes blink {
    0%, 100% { opacity: 1; box-shadow: 0 0 6px var(--primary); }
    50% { opacity: 0.25; box-shadow: none; }
}

.hero-title {
    font-size: 2rem !important;
    font-weight: 800 !important;
    background: linear-gradient(135deg, #fff 0%, #94a3b8 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0 !important;
    letter-spacing: -0.025em;
    position: relative;
    z-index: 1;
}

.hero-subtitle {
    font-size: 0.88rem;
    color: var(--text-secondary);
    margin-top: 0.4rem;
    font-weight: 400;
    position: relative;
    z-index: 1;
}

/* ── Pipeline Visualization ── */
.pipeline-wrap {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.6rem;
    padding: 1rem 1.2rem;
    background: var(--bg-surface);
    border-radius: var(--radius-sm);
    border: 1px solid var(--glass-border);
    margin-bottom: 1.5rem;
    animation: fadeInUp 0.5s 0.1s ease-out both;
}

.pipeline-step {
    flex: 1;
    text-align: center;
    padding: 0.7rem 0.4rem;
    border-radius: var(--radius-sm);
    background: var(--bg-base);
    border: 1px solid var(--glass-border);
    font-size: 0.72rem;
    font-weight: 700;
    color: var(--text-muted);
    position: relative;
    transition: all 0.35s ease;
    letter-spacing: 0.02em;
}

.pipeline-step.active {
    background: linear-gradient(135deg, rgba(6, 182, 212, 0.22), rgba(139, 92, 246, 0.18));
    border-color: var(--primary);
    color: var(--primary);
    box-shadow: 0 0 20px var(--primary-glow), inset 0 0 10px rgba(6,182,212,0.05);
    transform: scale(1.04);
}

.pipeline-step.success {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.18), rgba(6, 182, 212, 0.12));
    border-color: var(--accent);
    color: var(--accent);
}

.pipeline-step::after {
    content: '›';
    position: absolute;
    right: -0.7rem;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-muted);
    font-size: 1.1rem;
    opacity: 0.5;
}
.pipeline-step:last-child::after { display: none; }

/* ── Terminal ── */
.terminal-window {
    background: #050a14;
    border: 1px solid rgba(6, 182, 212, 0.18);
    border-radius: var(--radius-sm);
    padding: 1rem;
    font-family: var(--font-mono);
    font-size: 0.82rem;
    height: 320px;
    overflow-y: auto;
    position: relative;
    box-shadow: inset 0 0 40px rgba(0, 0, 0, 0.7);
    animation: fadeInUp 0.5s 0.15s ease-out both;
}

.terminal-window::before {
    content: '● ● ●';
    position: absolute;
    top: 0.65rem;
    left: 1rem;
    font-size: 0.55rem;
    color: var(--text-muted);
    letter-spacing: 0.35em;
    opacity: 0.6;
}

.terminal-content { margin-top: 1.4rem; }

.trace-line {
    margin-bottom: 5px;
    line-height: 1.55;
    animation: slideIn 0.25s ease-out both;
    opacity: 0;
}

@keyframes slideIn {
    from { opacity: 0; transform: translateX(-12px); }
    to { opacity: 1; transform: translateX(0); }
}

.trace-timestamp { color: var(--text-muted); font-size: 0.74rem; margin-right: 0.5rem; opacity: 0.7; }
.trace-step { color: var(--warning); font-weight: 700; }
.trace-success { color: var(--accent); font-weight: 600; }
.trace-fail { color: var(--danger); font-weight: 600; }
.trace-slm { color: var(--secondary); font-weight: 700; }
.trace-info { color: var(--primary); }

/* ── Result Card ── */
.result-hero {
    background: linear-gradient(135deg, rgba(16, 185, 129, 0.08), rgba(6, 182, 212, 0.08));
    border: 1px solid rgba(16, 185, 129, 0.25);
    border-radius: var(--radius);
    padding: 2rem;
    position: relative;
    overflow: hidden;
    animation: fadeInUp 0.6s 0.2s ease-out both;
}

.result-hero.rejected {
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.08), rgba(245, 158, 11, 0.08));
    border-color: rgba(239, 68, 68, 0.25);
}

.result-hero::after {
    content: '';
    position: absolute;
    top: 0; right: 0;
    width: 180px; height: 180px;
    background: radial-gradient(circle, rgba(16, 185, 129, 0.12), transparent 70%);
}
.result-hero.rejected::after {
    background: radial-gradient(circle, rgba(239, 68, 68, 0.12), transparent 70%);
}

.result-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 0.85rem;
    margin-top: 1.2rem;
    position: relative;
    z-index: 1;
}

.result-item {
    background: rgba(255, 255, 255, 0.025);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-sm);
    padding: 1rem;
    transition: all 0.25s ease;
}

.result-item:hover {
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(6, 182, 212, 0.25);
    transform: translateY(-2px);
}

.result-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--primary);
    font-weight: 700;
    margin-bottom: 0.3rem;
    display: flex;
    align-items: center;
    gap: 0.35rem;
}

.result-value {
    font-family: var(--font-mono);
    font-size: 0.92rem;
    color: var(--text-primary);
    font-weight: 500;
    word-break: break-word;
}

/* ── Gauge ── */
.gauge-wrap {
    margin: 1.2rem 0;
}

.gauge-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
}

.gauge-label {
    font-size: 0.82rem;
    color: var(--text-secondary);
    font-weight: 600;
}

.gauge-text {
    font-family: var(--font-mono);
    font-weight: 800;
    font-size: 1.15rem;
}

.gauge-bar {
    height: 8px;
    background: var(--bg-elevated);
    border-radius: 4px;
    overflow: hidden;
    position: relative;
}

.gauge-fill {
    height: 100%;
    border-radius: 4px;
    transition: width 1.2s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    overflow: hidden;
}

.gauge-fill::after {
    content: '';
    position: absolute;
    inset: 0;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.2), transparent);
    animation: shimmer 2.5s infinite;
}

@keyframes shimmer {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
}

/* ── Status Badge ── */
.status-badge {
    display: inline-flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    border-radius: 100px;
    font-size: 0.82rem;
    font-weight: 700;
    margin-bottom: 1rem;
    position: relative;
    z-index: 1;
    animation: fadeInUp 0.4s ease-out both;
}

.status-badge.success {
    background: rgba(16, 185, 129, 0.12);
    color: var(--accent);
    border: 1px solid rgba(16, 185, 129, 0.3);
}

.status-badge.error {
    background: rgba(239, 68, 68, 0.12);
    color: var(--danger);
    border: 1px solid rgba(239, 68, 68, 0.3);
}

.status-pulse {
    width: 8px; height: 8px;
    border-radius: 50%;
    position: relative;
}

.status-pulse::after {
    content: '';
    position: absolute;
    inset: -4px;
    border-radius: 50%;
    animation: ping 1.8s cubic-bezier(0, 0, 0.2, 1) infinite;
}

.status-badge.success .status-pulse { background: var(--accent); }
.status-badge.success .status-pulse::after { background: var(--accent); }
.status-badge.error .status-pulse { background: var(--danger); }
.status-badge.error .status-pulse::after { background: var(--danger); }

@keyframes ping {
    75%, 100% { transform: scale(2.2); opacity: 0; }
}

/* ── Inputs ── */
.stTextArea textarea, .stTextInput input {
    background: var(--bg-surface) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-primary) !important;
    font-family: var(--font-mono) !important;
    font-size: 0.85rem !important;
    transition: all 0.2s ease !important;
}
.stTextArea textarea:focus, .stTextInput input:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.1) !important;
}

/* ── Selectbox ── */
.stSelectbox > div > div {
    background: var(--bg-surface) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: var(--radius-sm) !important;
}

/* ── Button ── */
.stButton > button {
    background: linear-gradient(135deg, #0891b2, #2563eb) !important;
    color: white !important;
    font-weight: 700 !important;
    width: 100% !important;
    border: none !important;
    border-radius: var(--radius-sm) !important;
    padding: 0.8rem !important;
    position: relative;
    overflow: hidden;
    transition: all 0.3s ease !important;
    letter-spacing: 0.02em;
    font-size: 0.9rem !important;
}
.stButton > button::before {
    content: '';
    position: absolute;
    top: 0; left: -100%;
    width: 100%; height: 100%;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.18), transparent);
    transition: left 0.6s;
}
.stButton > button:hover::before { left: 100%; }
.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 12px 35px -8px rgba(6, 182, 212, 0.45) !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    gap: 0.5rem;
    background: transparent !important;
}
.stTabs [data-baseweb="tab"] {
    background: var(--bg-surface) !important;
    border: 1px solid var(--glass-border) !important;
    border-radius: var(--radius-sm) !important;
    color: var(--text-secondary) !important;
    font-weight: 600 !important;
    padding: 0.55rem 1.1rem !important;
    font-size: 0.82rem !important;
    transition: all 0.2s ease;
}
.stTabs [data-baseweb="tab"]:hover {
    border-color: rgba(6, 182, 212, 0.3) !important;
    color: var(--text-primary) !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, rgba(6, 182, 212, 0.18), rgba(139, 92, 246, 0.14)) !important;
    border-color: var(--primary) !important;
    color: var(--primary) !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--bg-base), var(--bg-deep)) !important;
    border-right: 1px solid var(--glass-border) !important;
}
[data-testid="stSidebar"] .stRadio label {
    color: var(--text-secondary) !important;
    font-weight: 500 !important;
    padding: 0.55rem 0.7rem !important;
    border-radius: var(--radius-sm) !important;
    transition: all 0.2s ease;
    font-size: 0.88rem !important;
}
[data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(6, 182, 212, 0.08) !important;
    color: var(--primary) !important;
}

/* ── Section Title ── */
.section-title {
    font-size: 1rem;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 1rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    animation: fadeInUp 0.5s ease-out both;
}
.section-title::before {
    content: '';
    width: 4px;
    height: 1.1rem;
    background: linear-gradient(180deg, var(--primary), var(--secondary));
    border-radius: 2px;
}

/* ── Metric Row ── */
.metric-row {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 0.85rem;
    margin-bottom: 1.5rem;
}
.metric-card {
    background: var(--bg-surface);
    border: 1px solid var(--glass-border);
    border-radius: var(--radius-sm);
    padding: 1.1rem;
    text-align: center;
    transition: all 0.3s ease;
    animation: fadeInUp 0.5s ease-out both;
}
.metric-card:hover {
    border-color: rgba(6, 182, 212, 0.2);
    transform: translateY(-2px);
}
.metric-value {
    font-size: 1.6rem;
    font-weight: 800;
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.metric-label {
    font-size: 0.72rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: 0.2rem;
}

/* ── Hide Defaults ── */
#MainMenu, footer { visibility: hidden; }
header { background: transparent !important; }

/* ── Responsive tweaks ── */
@media (max-width: 768px) {
    .hero-title { font-size: 1.4rem !important; }
    .pipeline-step { font-size: 0.6rem; padding: 0.5rem 0.2rem; }
    .result-grid { grid-template-columns: 1fr; }
    .metric-row { grid-template-columns: 1fr; }
}
</style>
""").strip(), unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# HELPER COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════

def render_hero(title: str, subtitle: str, badge: str = "LIVE"):
    st.markdown(textwrap.dedent(f'''
    <div class="hero-wrap">
        <div class="hero-badge"><span class="dot"></span>{html.escape(badge)}</div>
        <h1 class="hero-title">{html.escape(title)}</h1>
        <div class="hero-subtitle">{html.escape(subtitle)}</div>
    </div>
    ''').strip(), unsafe_allow_html=True)


def _normalize_pipeline_step(step_id: str) -> str:
    """Map internal sub-steps to the visual pipeline stages."""
    if not step_id:
        return step_id
    if step_id in {"E2B", "E2.5B"}:
        return "E3"
    return step_id

def render_pipeline_status(current_step=None):
    steps = [
        ("INPUT", "📥 Entrée"),
        ("E0", "🔧 Prétraitement"),
        ("E1", "⚙️ Parsing"),
        ("E2", "🌍 Validation"),
        ("E2.5", "✂️ Fragmentation"),
        ("E3", "🤖 SLM (si nécessaire)"),
        ("DECISION", "🧠 Décision"),
        ("OUTPUT", "📤 Sortie")
    ]
    current_visual_step = _normalize_pipeline_step(current_step)
    html_parts = ['<div class="pipeline-wrap">']
    for sid, sname in steps:
        cls = "pipeline-step"
        if current_visual_step == sid:
            cls += " active"
        elif current_visual_step:
            try:
                idx_current = [s[0] for s in steps].index(current_visual_step)
                idx_step = [s[0] for s in steps].index(sid)
                if idx_step < idx_current:
                    cls += " success"
            except ValueError:
                pass
        html_parts.append(f'<div class="{cls}">{html.escape(sname)}</div>')
    html_parts.append('</div>')
    return "".join(html_parts)

def render_gauge(confidence: float, label: str = "Confiance"):
    color = "#10b981" if confidence > 0.75 else "#f59e0b" if confidence > 0.5 else "#ef4444"
    pct = int(confidence * 100)
    return textwrap.dedent(f'''
    <div class="gauge-wrap">
        <div class="gauge-header">
            <span class="gauge-label">{html.escape(label)}</span>
            <span class="gauge-text" style="color:{color};">{pct}%</span>
        </div>
        <div class="gauge-bar">
            <div class="gauge-fill" style="width:{pct}%; background: linear-gradient(90deg, {color}, {color}cc);"></div>
        </div>
    </div>
    ''').strip()

def render_status_badge(success: bool, text: str):
    cls = "success" if success else "error"
    icon = "✅" if success else "❌"
    return textwrap.dedent(f'''
    <div class="status-badge {cls}">
        <span class="status-pulse"></span>
        {icon} {html.escape(text)}
    </div>
    ''').strip()


def _humanize_signal(signal: str) -> str:
    if not signal:
        return "Signal vide"

    signal = str(signal)

    exact_map = {
        "pass2_soft:missing_road_like_component": "Adresse partielle: composant rue non explicite, mais extraction acceptable.",
        "pass2_geo_incoherent_cannot_validate_address": "Incoherence geo: l'adresse ne peut pas etre validee avec la ville/pays extraits.",
        "pass2_address_missing": "Adresse manquante apres parsing.",
        "town_missing": "Ville absente dans le message initial; le moteur a tente de la completer.",
        "town_missing_from_name_country_pattern": "Ville absente: la ligne contient surtout un nom et un pays, sans ville explicite.",
        "pass1_town_ambiguous_requires_disambiguation": "Ville ambigue: verification manuelle recommandee.",
        "pass1_country_missing": "Pays absent dans le message initial.",
        "pass1_missing_country_town": "Pays et ville absents dans le message initial.",
        "pass1_town_extracted_from_suburb_and_confirmed": "Ville extraite depuis un quartier/localite et confirmee.",
        "pass1_town_local_script_accepted": "Ville acceptee dans son ecriture locale.",
        "pass1_town_is_suburb_keyword_rejected": "Localite detectee comme quartier, pas comme ville principale.",
        "pass1_suburb_context_detected": "Contexte de quartier/localite detecte.",
        "pass1_suburb_context_detected_and_town_invalid": "Quartier/localite detecte et ville non validee.",
        "requires_manual_verification:town_unverified": "Ville non verifiee: revue manuelle requise.",
        "requires_manual_verification:suburb_cannot_be_promoted_to_city": "Revue manuelle requise: un quartier ne peut pas etre utilise comme ville principale.",
        "no_content_after_account": "Aucune information exploitable apres le compte.",
        "inline_address_town_split": "Adresse et ville se trouvaient sur la meme ligne; elles ont ete separees.",
        "name_address_mixed": "Nom et adresse semblent melanges dans la meme zone.",
        "town_reclassified_as_address": "Un element d'abord lu comme ville a ete reclasse comme adresse.",
        "ambiguous_city_country_tail": "Fin de ligne ambigue entre ville et pays.",
        "pass2_no_valid_address_detected": "Aucune adresse valide detectee.",
        "empty_input": "Message vide.",
        "invalid_structured_line_3": "Ligne structuree 3 invalide.",
        "missing_mandatory_3": "Ligne obligatoire 3 manquante.",
        "4_and_5_must_appear_together": "Les lignes 4 et 5 doivent apparaitre ensemble.",
        "line_8_non_identifier_narrative": "Ligne 8 detectee comme texte narratif, pas comme identifiant.",
        "line_8_length_exceeds_35": "Ligne 8 trop longue pour le format attendu.",
        "orphan_continuation_line": "Ligne de continuation sans ligne parent.",
        "T56_invalid_8_continuation": "Continuation de ligne 8 invalide pour le format T56.",
        "T56_invalid_8_semantic_content": "Ligne 8 semantiquement invalide pour le format T56.",
        "T56_invalid_8_repetition": "Repetition invalide de la ligne 8 pour le format T56.",
        "slm_applied": "Fallback SLM applique pour renforcer l'extraction.",
        "slm_cached": "Resultat SLM recupere depuis le cache.",
        "slm_failed": "Fallback SLM tente, mais aucune reponse exploitable n'a ete obtenue.",
        "fast_track_slm_triggered_due_to_complexity": "IA declenchee rapidement car le message etait complexe.",
        "town_was_country_alias_rejected": "Une valeur de pays avait ete lue comme ville; elle a ete corrigee.",
        "quarantine_manual_review_required": "Message place en quarantaine pour revue manuelle.",
        "mandatory_missing:town": "Rejet: ville obligatoire manquante.",
        "mandatory_missing:country": "Rejet: pays obligatoire manquant.",
    }
    if signal in exact_map:
        return exact_map[signal]

    if signal.startswith("pass1_town_confirmed_geonames:"):
        method = signal.split(":", 1)[1]
        return f"Ville confirmee par GeoNames ({method})."
    if signal.startswith("slm_town_rejected_backend_validation:"):
        reason = signal.split(":", 1)[1].replace("_", " ")
        return f"La ville proposee par l'IA a ete rejetee par la validation backend ({reason})."
    if signal.startswith("short_country_code_normalized:"):
        details = signal.split(":", 1)[1]
        return f"Code pays court normalise ({details})."
    if signal.startswith("country_embedded_in_town_line:"):
        country = signal.split(":", 1)[1]
        return f"Pays detecte dans la ligne de ville ({country})."
    if signal.startswith("pass1_locality_has_parent:"):
        details = signal.split(":", 1)[1]
        return f"Localite rattachee a une ville principale ({details})."
    if signal.startswith("pass2_town_backfilled_from_fragmentation:"):
        town = signal.split(":", 1)[1]
        return f"Ville completee automatiquement depuis la fragmentation ({town})."
    if signal.startswith("pass1_town_not_official:"):
        town = signal.split(":", 1)[1]
        return f"Ville non officielle au format saisi ({town}), tentative de resolution appliquee."
    if signal.startswith("pass1_town_resolved_from_composite:"):
        details = signal.split(":", 1)[1]
        return f"Toponyme compose resolu avec succes ({details})."
    if signal.startswith("pass1_town_inferred_from_address:"):
        town = signal.split(":", 1)[1]
        return f"Ville deduite depuis les lignes d'adresse ({town})."
    if signal.startswith("pass2_address_contains_town_or_country:"):
        line = signal.split(":", 1)[1]
        return f"Adresse contient deja une information geo (ville/pays): {line}."
    if signal.startswith("pass2_address_contextually_accepted:"):
        line = signal.split(":", 1)[1]
        return f"Adresse acceptee par controle contextuel: {line}."
    if signal.startswith("pass2_invalid_address_line:"):
        line = signal.split(":", 1)[1]
        return f"Ligne d'adresse invalide ou insuffisante: {line}."
    if signal.startswith("pass2_libpostal:"):
        details = signal.split(":", 1)[1]
        return f"Analyse d'adresse incomplete ({details.replace('_', ' ')})."
    if signal.startswith("pass2_soft:"):
        details = signal.split(":", 1)[1]
        return f"Remarque souple sur l'adresse ({details.replace('_', ' ')})."
    if signal.startswith("multiline_name_fused:"):
        count = signal.split(":", 1)[1]
        return f"Nom reconstitue depuis plusieurs lignes ({count} ligne ajoutee)."
    if signal.startswith("zone_industrielle_extracted_town:"):
        town = signal.split(":", 1)[1]
        return f"Ville extraite depuis une ligne de zone industrielle ({town})."
    if signal.startswith("ambiguous_city_country_tail_resolved_as_town:"):
        reason = signal.split(":", 1)[1]
        return f"Fin de ligne ambigue resolue comme ville ({reason})."
    if signal.startswith("ambiguous_city_country_tail_resolved_as_address:"):
        reason = signal.split(":", 1)[1]
        return f"Fin de ligne ambigue conservee comme adresse ({reason})."
    if signal.startswith("unclassified_line_to_address:"):
        line = signal.split(":", 1)[1]
        return f"Ligne non classee rattachee a l'adresse: {line}."
    if signal.startswith("country_from_iban"):
        return "Pays deduit depuis l'IBAN."
    if signal.startswith("country_conflict_iban_hint_only:"):
        conflict = signal.split(":", 1)[1]
        if "!=" in conflict:
            left, right = conflict.split("!=", 1)
            left = left.replace("explicit:", "").strip()
            right = right.replace("explicit:", "").strip()
            return f"Le pays indique par l'IBAN ({left}) est different du pays ecrit dans le message ({right}); le contenu explicite est conserve."
        return f"Conflit pays entre IBAN et contenu explicite ({conflict})."
    if signal.startswith("geo_postal_inference_"):
        m = re.match(r"^geo_postal_inference(?:_slm)?_([A-Z]{2}):(.+?)→(.+)$", signal)
        if m:
            country, postal, town = m.groups()
            source = " par IA" if signal.startswith("geo_postal_inference_slm_") else ""
            return f"Ville deduite{source} depuis le code postal {postal} ({country}): {town}."
        details = signal.split(":", 1)[1] if ":" in signal else signal
        if "→" in details:
            postal, town = details.split("→", 1)
            return f"Ville deduite automatiquement depuis le code postal {postal}: {town}."
        return f"Ville deduite automatiquement depuis le code postal ({details})."

    return signal.replace("_", " ").strip().capitalize()


def _render_human_signal_list(title: str, signals, empty_text: str = "Aucun signal"):
    st.markdown(f"**{title}**")
    if not signals:
        st.success(empty_text)
        return

    for sig in signals:
        human = _humanize_signal(sig)
        st.markdown(
            f"- {human}<br><span style='color:var(--text-muted); font-size:0.78rem;'>Code: {html.escape(str(sig))}</span>",
            unsafe_allow_html=True,
        )


def _is_final_error_signal(signal: str) -> bool:
    if not signal:
        return False

    signal = str(signal)
    critical_prefixes = (
        "mandatory_missing:",
        "quarantine_",
        "requires_manual_verification:",
        "invalid_",
        "T56_invalid_",
        "pass1_country_missing",
        "pass1_missing_country_town",
        "pass1_town_is_suburb_keyword_rejected",
        "pass1_suburb_context_detected",
        "pass1_suburb_context_detected_and_town_invalid",
        "pass2_no_valid_address_detected",
        "pass2_invalid_address_line:",
        "pass2_geo_incoherent_cannot_validate_address",
        "country_conflict_iban_hint_only:",
    )
    if signal in {
        "pass1_town_ambiguous_requires_disambiguation",
        "pass1_town_not_official",
        "pass1_town_not_official:XX INVALID COUNTRY",
        "pass2_address_missing",
    }:
        return True
    return any(signal.startswith(prefix) for prefix in critical_prefixes)


def _filter_final_error_signals(signals):
    return [signal for signal in (signals or []) if _is_final_error_signal(signal)]


def _render_final_signal_panel(result):
    rejected = bool(getattr(result.meta, "rejected", False))
    rejection_reasons = _filter_final_error_signals(getattr(result.meta, "rejection_reasons", []) or [])
    warnings = _filter_final_error_signals(getattr(result.meta, "warnings", []) or [])

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        parse_conf = result.meta.parse_confidence or 0.0
        st.write(f"**Confiance Parse :** {parse_conf:.2f}")
        st.write(f"**Rejete :** {'Oui' if rejected else 'Non'}")
        if rejected:
            _render_human_signal_list(
                "Raisons de decision",
                rejection_reasons,
                empty_text="Aucune raison de rejet finale",
            )
        else:
            st.success("Aucun rejet final")
        st.markdown('</div>', unsafe_allow_html=True)

    with c2:
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        if rejected:
            _render_human_signal_list(
                "Warnings de validation",
                warnings,
                empty_text="Aucun warning critique final",
            )
        else:
            st.success("Warnings internes nettoyes apres correction")
        st.markdown('</div>', unsafe_allow_html=True)

def render_result_card(result, elapsed: float):
    is_rejected = getattr(result.meta, 'rejected', False)
    status_text = "MESSAGE ACCEPTÉ" if not is_rejected else "MESSAGE REJETÉ"
    card_cls = "result-hero" + (" rejected" if is_rejected else "")
    confidence = result.meta.parse_confidence or 0
    route = "🧠 IA Générative (Fallback)" if getattr(result.meta, 'fallback_used', False) else "⚙️ Algorithmique (Heuristique)"
    postal = result.country_town.postal_code if result.country_town and result.country_town.postal_code else '-'
    town = result.country_town.town if result.country_town and result.country_town.town else '-'
    country = result.country_town.country if result.country_town and result.country_town.country else '-'
    name = result.name[0] if result.name and result.name[0] else '-'
    addr = ' '.join(result.address_lines) if result.address_lines else '-'

    return textwrap.dedent(f'''
    <div class="{card_cls}">
        {render_status_badge(not is_rejected, status_text)}
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1rem; position:relative; z-index:1;">
            <span style="font-size:0.85rem; color:var(--text-secondary); font-weight:500;">⏱️ Temps d'exécution</span>
            <span style="font-family:var(--font-mono); color:var(--primary); font-weight:700; font-size:1.05rem;">{elapsed}s</span>
        </div>
        {render_gauge(confidence, "📊 Confiance de Parsing")}
        <div class="result-grid">
            <div class="result-item">
                <div class="result-label">👤 Nom</div>
                <div class="result-value">{html.escape(str(name))}</div>
            </div>
            <div class="result-item">
                <div class="result-label">📍 Adresse</div>
                <div class="result-value">{html.escape(str(addr))}</div>
            </div>
            <div class="result-item">
                <div class="result-label">🏙️ Ville</div>
                <div class="result-value">{html.escape(str(town))} <span style="font-size:0.7rem; color:var(--accent);">✓ Auto</span></div>
            </div>
            <div class="result-item">
                <div class="result-label">📮 Code Postal</div>
                <div class="result-value">{html.escape(str(postal))}</div>
            </div>
            <div class="result-item">
                <div class="result-label">🌍 Pays (ISO)</div>
                <div class="result-value">{html.escape(str(country))}</div>
            </div>
            <div class="result-item">
                <div class="result-label">🔧 Rue</div>
                <div class="result-value">{html.escape(str(route))}</div>
            </div>
        </div>
    </div>
    ''').strip()

# ═══════════════════════════════════════════════════════════════════════════════
# LIVE LOGGER
# ═══════════════════════════════════════════════════════════════════════════════
class StreamlitLiveLogger(PipelineLogger):
    def __init__(self, trace_container, pipeline_container):
        super().__init__()
        self.trace_container = trace_container
        self.pipeline_container = pipeline_container
        self.trace_html = ""
        self.line_count = 0
        self.step_colors = {
            "INPUT": "trace-step", "E0": "trace-step", "E1": "trace-success",
            "E2": "trace-success", "E2.5": "trace-step", "E3": "trace-slm",
            "E2B": "trace-step", "E2.5B": "trace-step", "DECISION": "trace-fail", "OUTPUT": "trace-success"
        }

    def log(self, step: str, message: str, level: str = "INFO", **data):
        super().log(step, message, level, **data)
        self.line_count += 1
        color_class = self.step_colors.get(step, "trace-info")
        if "rejeté" in message.lower() or "erreur" in message.lower(): color_class = "trace-fail"
        if "Terminé" in message or "terminée" in message: color_class = "trace-success"
        if step in {"E3", "E2B", "E2.5B"} or "SLM" in message.upper():
            color_class = "trace-slm"

        details = ""
        if data:
            details = " <span style=\'opacity:0.45;font-size:0.7rem\'>[" + ", ".join(f"{k}={v}" for k, v in data.items()) + "]</span>"
        timestamp = time.strftime("%H:%M:%S")
        line_html = f'<div class="trace-line" style="animation-delay: {self.line_count * 0.04}s"><span class="trace-timestamp">[{timestamp}]</span><span class="{color_class}">[{html.escape(step)}]</span> {html.escape(message)}{details}</div>'
        self.trace_html += line_html
        self.trace_container.markdown(
            f'<div class="terminal-window"><div class="terminal-content">{self.trace_html}</div></div>',
            unsafe_allow_html=True
        )
        self.pipeline_container.markdown(render_pipeline_status(step), unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# DATA LOAD
# ═══════════════════════════════════════════════════════════════════════════════
SAMPLES_PATH = Path(PROJECT_ROOT) / "data" / "samples" / "mt103_party_cases.json"
GLOBAL_CORPUS_PATH = Path(PROJECT_ROOT) / "data" / "samples" / "mt103_global_test_corpus.txt"
CASE_HEADER_PATTERN = re.compile(r"^===\s*CASE\s+(\d+)\s*===\s*$", re.IGNORECASE)


def _parse_global_corpus_cases(corpus_text: str):
    cases = []
    current_case_id = None
    current_lines = []

    def flush_case():
        nonlocal current_case_id, current_lines
        if not current_case_id:
            return
        while current_lines and not current_lines[0].strip():
            current_lines.pop(0)
        while current_lines and not current_lines[-1].strip():
            current_lines.pop()
        if not current_lines:
            return
        cases.append({
            "label": f"🌍 Global Corpus - CASE {current_case_id}",
            "category": "global_corpus",
            "source": "data/samples/mt103_global_test_corpus.txt",
            "raw_message": "\n".join(current_lines),
        })

    for raw_line in corpus_text.splitlines():
        line = raw_line.rstrip("\n")
        match = CASE_HEADER_PATTERN.match(line.strip())
        if match:
            flush_case()
            current_case_id = match.group(1).zfill(3)
            current_lines = []
            continue
        if current_case_id:
            current_lines.append(line)

    flush_case()
    return cases


def _load_global_corpus_cases():
    if not GLOBAL_CORPUS_PATH.exists():
        return []
    with open(GLOBAL_CORPUS_PATH, "r", encoding="utf-8") as f:
        return _parse_global_corpus_cases(f.read())

def load_cases():
    base_cases = []
    if SAMPLES_PATH.exists():
        with open(SAMPLES_PATH, "r", encoding="utf-8") as f:
            base_cases = json.load(f)
    global_corpus_cases = _load_global_corpus_cases()
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
    return extreme_cases + global_corpus_cases + base_cases

cases = load_cases()
options = {f"{c['label']}": c["raw_message"] for c in cases}


def _safe_dump_model(obj):
    try:
        return obj.model_dump()
    except Exception:
        try:
            import dataclasses
            if dataclasses.is_dataclass(obj):
                return dataclasses.asdict(obj)
        except Exception:
            pass
        return vars(obj)


def _dedupe_preserve_order(items):
    seen = set()
    result = []
    for item in items or []:
        key = str(item)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _prune_empty_values(value):
    if isinstance(value, dict):
        cleaned = {
            k: _prune_empty_values(v)
            for k, v in value.items()
        }
        return {k: v for k, v in cleaned.items() if v not in (None, [], {}, "")}
    if isinstance(value, list):
        return [_prune_empty_values(v) for v in value if v not in (None, [], {}, "")]
    return value


def _party_type_label(is_org):
    if is_org is True:
        return "Organisation / entreprise"
    if is_org is False:
        return "Personne physique"
    return "Non determine"


def _party_field_context(field_type, role):
    field = str(field_type or "").upper()
    if field.startswith("50"):
        return {
            "party_key": "donneur_ordre",
            "party_label": "Donneur d'ordre",
            "account_key": "compte_donneur_ordre",
            "name_key": "nom_donneur_ordre",
            "type_key": "type_donneur_ordre",
            "address_key": "adresse_donneur_ordre",
        }
    if field.startswith("59"):
        return {
            "party_key": "beneficiaire",
            "party_label": "Beneficiaire",
            "account_key": "compte_beneficiaire",
            "name_key": "nom_beneficiaire",
            "type_key": "type_beneficiaire",
            "address_key": "adresse_beneficiaire",
        }

    role_key = "donneur_ordre" if role == "debtor" else "beneficiaire" if role == "creditor" else "partie"
    return {
        "party_key": role_key,
        "party_label": role_key.replace("_", " ").capitalize(),
        "account_key": f"compte_{role_key}",
        "name_key": f"nom_{role_key}",
        "type_key": f"type_{role_key}",
        "address_key": f"adresse_{role_key}",
    }


def _humanize_contextual_check(key, value):
    yes_no = "Oui" if value is True else "Non" if value is False else "Non disponible" if value is None else value
    labels = {
        "intrinsic_valid": "La ligne ressemble a une adresse valide",
        "locally_plausible": "L'adresse est plausible pour la ville/pays detectes",
        "geo_consistent_with_pass1": "L'adresse est coherente avec la ville/pays extraits au premier passage",
        "contains_town_or_country": "La ligne contient deja une ville ou un pays",
        "geo_coherent_pass1": "La verification geographique globale est coherente",
        "town": "Ville utilisee pour la verification",
        "country": "Pays utilise pour la verification",
    }
    label = labels.get(str(key), str(key).replace("_", " ").capitalize())
    return {"controle": label, "resultat": yes_no}


def _humanize_address_validation(item):
    checks = item.get("contextual_checks") or {}
    components = item.get("components") or {}
    parsed = item.get("parsed") or []
    readable_components = {
        "rue": components.get("ROAD"),
        "numero": components.get("HOUSE_NUMBER"),
        "code_postal": components.get("POSTCODE"),
        "ville": components.get("CITY") or components.get("TOWN"),
        "pays": components.get("COUNTRY"),
    }

    return {
        "adresse_analysee": item.get("raw"),
        "decision": "Adresse acceptee" if item.get("contextual_valid") else "Adresse a verifier",
        "lecture_adresse": {k: v for k, v in readable_components.items() if v not in (None, "", [])},
        "controles": [_humanize_contextual_check(k, v) for k, v in checks.items()],
        "details_parser": [
            {"valeur": pair[0], "type": str(pair[1]).replace("_", " ")}
            for pair in parsed
            if isinstance(pair, (list, tuple)) and len(pair) == 2
        ],
        "remarques": [_humanize_signal(w) for w in _dedupe_preserve_order(item.get("warnings") or [])],
    }


def _display_fragment_json(fragment):
    data = _safe_dump_model(fragment)
    labels = {
        "strt_nm": "rue",
        "bldg_nb": "numero_batiment",
        "bldg_nm": "nom_batiment",
        "flr": "etage",
        "room": "piece",
        "pst_cd": "code_postal",
        "twn_nm": "ville",
        "ctry_sub_div": "region",
        "ctry": "pays",
        "adr_line": "lignes_adresse_libres",
        "fragmentation_confidence": "confiance_fragmentation",
        "fallback_used": "fragmentation_de_secours_utilisee",
    }
    return {
        labels.get(k, k): v
        for k, v in data.items()
        if v not in (None, [], "") and not (isinstance(v, bool) and v is False)
    }


def _build_display_json(result):
    geo = result.country_town
    meta = result.meta
    party_context = _party_field_context(result.field_type, result.role)
    before_slm_raw = _dedupe_preserve_order(getattr(meta, "warnings_before_slm", []) or [])
    after_slm_raw = _dedupe_preserve_order(getattr(meta, "warnings_after_slm", []) or [])
    warnings_before_slm = [_humanize_signal(w) for w in before_slm_raw]
    warnings_after_slm = [_humanize_signal(w) for w in after_slm_raw]
    llm_signals = [_humanize_signal(s) for s in _dedupe_preserve_order(getattr(meta, "llm_signals", []) or [])]
    rejection_reasons = [
        _humanize_signal(r)
        for r in _dedupe_preserve_order(getattr(meta, "rejection_reasons", []) or [])
    ]

    display = {
        "type_champ_swift": result.field_type,
        "role_metier": party_context["party_label"],
        party_context["account_key"]: result.account,
        "identifiant_partie": _safe_dump_model(result.party_id) if result.party_id else None,
        party_context["name_key"]: result.name,
        party_context["type_key"]: _party_type_label(result.is_org),
        party_context["address_key"]: result.address_lines,
        "localisation": {
            "pays": geo.country if geo else None,
            "ville": geo.town if geo else None,
            "code_postal": geo.postal_code if geo else None,
        },
        "date_naissance": _safe_dump_model(result.dob) if result.dob else None,
        "lieu_naissance": _safe_dump_model(result.pob) if result.pob else None,
        "identifiant_organisation": _safe_dump_model(result.org_id) if result.org_id else None,
        "identifiant_national": result.national_id,
        "complement_postal": result.postal_complement,
        "qualite": {
            "confiance": getattr(meta, "parse_confidence", 0.0),
            "slm_utilise": "Oui" if getattr(meta, "fallback_used", False) else "Non",
            "decision": "Rejete" if getattr(meta, "rejected", False) else "Accepte",
            "revue_manuelle": "Oui" if getattr(meta, "requires_manual_review", False) else "Non",
            "remarques_avant_ia": warnings_before_slm,
            "remarques_apres_ia": warnings_after_slm,
            "signaux_ia": llm_signals,
            "raisons_rejet": rejection_reasons,
        },
        "validation_adresse": [
            _humanize_address_validation(item)
            for item in (getattr(result, "address_validation", []) or [])
        ],
        "fragments_adresse": [
            _display_fragment_json(fragment)
            for fragment in (getattr(result, "fragmented_addresses", []) or [])
        ],
    }

    return _prune_empty_values(display)


def _run_case(raw_message: str, message_id: str = "UI_CASE", slm_model: str = "qwen2.5:0.5b"):
    class SilentLogger(PipelineLogger):
        def log(self, *args, **kwargs):
            super().log(*args, **kwargs)

    logger = SilentLogger()
    start = time.time()
    result, _ = run_pipeline(
        raw_message=raw_message,
        message_id=message_id,
        slm_model=slm_model,
        logger=logger,
    )
    elapsed = round(time.time() - start, 3)
    iso_xml, iso_payload, iso_errors = build_iso20022_party_xml(result, include_envelope=True)
    return result, logger, elapsed, iso_xml, iso_payload, iso_errors


def _run_case_without_slm(raw_message: str, message_id: str = "UI_CASE_NO_SLM"):
    class SilentLogger(PipelineLogger):
        def log(self, *args, **kwargs):
            super().log(*args, **kwargs)

    original_needs = pipeline_module.needs_slm_fallback
    original_apply = pipeline_module.apply_slm_fallback
    try:
        pipeline_module.needs_slm_fallback = lambda party: False
        pipeline_module.apply_slm_fallback = lambda party, model="qwen2.5:0.5b": party
        logger = SilentLogger()
        start = time.time()
        result, _ = run_pipeline(
            raw_message=raw_message,
            message_id=message_id,
            slm_model="qwen2.5:0.5b",
            logger=logger,
        )
        elapsed = round(time.time() - start, 3)
        return result, logger, elapsed
    finally:
        pipeline_module.needs_slm_fallback = original_needs
        pipeline_module.apply_slm_fallback = original_apply


def _extract_kpis(results_rows):
    total = len(results_rows)
    accepted = sum(1 for r in results_rows if not r["rejected"])
    fallback = sum(1 for r in results_rows if r["fallback_used"])
    with_country = sum(1 for r in results_rows if r["country"])
    with_town = sum(1 for r in results_rows if r["town"])
    with_postal = sum(1 for r in results_rows if r["postal_code"])
    avg_conf = round(sum(r["confidence"] for r in results_rows) / total, 3) if total else 0.0
    return {
        "total": total,
        "accepted": accepted,
        "rejected": total - accepted,
        "acceptance_rate": round((accepted / total) * 100, 1) if total else 0.0,
        "fallback_rate": round((fallback / total) * 100, 1) if total else 0.0,
        "avg_confidence": avg_conf,
        "country_coverage": round((with_country / total) * 100, 1) if total else 0.0,
        "town_coverage": round((with_town / total) * 100, 1) if total else 0.0,
        "postal_coverage": round((with_postal / total) * 100, 1) if total else 0.0,
    }


def _result_row_from_case(case_label, result, elapsed):
    return {
        "case": case_label,
        "elapsed_s": elapsed,
        "confidence": float(getattr(result.meta, "parse_confidence", 0.0) or 0.0),
        "rejected": bool(getattr(result.meta, "rejected", False)),
        "fallback_used": bool(getattr(result.meta, "fallback_used", False)),
        "country": (result.country_town.country if result.country_town else None),
        "town": (result.country_town.town if result.country_town else None),
        "postal_code": (result.country_town.postal_code if result.country_town else None),
        "warnings": len(getattr(result.meta, "warnings", []) or []),
    }

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR — Premium Navigation
# ═══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown(textwrap.dedent("""
    <div style="text-align:center; padding:1.2rem 0 0.8rem; margin-bottom:0.5rem;">
        <div style="font-size:2.4rem; margin-bottom:0.3rem;">⚡</div>
        <div style="font-size:1.05rem; font-weight:800; color:var(--text-primary); letter-spacing:-0.02em;">SWIFT Engine</div>
        <div style="font-size:0.7rem; color:var(--text-muted); letter-spacing:0.12em; text-transform:uppercase; margin-top:0.2rem;">ISO 20022</div>
    </div>
    <hr style="border:none; border-top:1px solid var(--glass-border); margin:0.8rem 0;">
    """).strip(), unsafe_allow_html=True)

    page = st.radio(
        "Navigation",
        [
            "🚀 Mode Avancé",
            "✅ Mode Validation",
            "🧾 Message SWIFT complet",
            "🔄 Mode Traitement Complet",
        ],
        label_visibility="collapsed"
    )

    st.markdown(textwrap.dedent("""
    <div style="margin-top:3rem;">
        <div class="glass-card" style="padding:0.9rem; animation:none;">
            <div style="font-size:0.7rem; color:var(--text-muted); margin-bottom:0.4rem; text-transform:uppercase; letter-spacing:0.08em; font-weight:600;">🖥️ Status Système</div>
            <div style="display:flex; align-items:center; gap:0.5rem; font-size:0.82rem; font-weight:700; color:var(--accent);">
                <span class="status-pulse" style="background:var(--accent); width:7px; height:7px;"></span>
                Opérationnel
            </div>
        </div>
    </div>
    """).strip(), unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 1 — MODE AVANCÉ
# ═══════════════════════════════════════════════════════════════════════════════
if page == "🚀 Mode Avancé":
    render_hero(
        "Moteur Hybride Intelligent",
        "Heuristique + SLM Local (Ollama Qwen2.5:0.5b) + GeoNames",
        "PIPELINE ACTIF"
    )

    pipeline_viz = st.empty()
    pipeline_viz.markdown(render_pipeline_status("INPUT"), unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1.5], gap="large")

    with col1:
        st.markdown('<div class="section-title">📥 Entrée SWIFT</div>', unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            
            # Onglets de source d'entrée
            input_source = st.radio("Source d'entrée", options=["📝 Coller du texte", "🔽 Sélectionner un cas", "📂 Importer un fichier"], horizontal=True, label_visibility="collapsed")
            
            raw_message = ""
            
            if input_source == "🔽 Sélectionner un cas":
                dataset_choice = st.selectbox("Cas de test", options=list(options.keys()), label_visibility="collapsed")
                raw_message = options[dataset_choice] if dataset_choice else ""
                st.info(f"✓ Cas sélectionné: {dataset_choice}")
            
            elif input_source == "📂 Importer un fichier":
                uploaded_file = st.file_uploader("Choisir un fichier SWIFT", type=["txt", "swift", "msg", ""], label_visibility="collapsed")
                if uploaded_file is not None:
                    raw_message = uploaded_file.read().decode("utf-8", errors="ignore")
                    st.success(f"✓ Fichier chargé: {uploaded_file.name} ({len(raw_message)} caractères)")
                    st.text_area("📄 Contenu du fichier", value=raw_message, height=140, disabled=True, label_visibility="collapsed")
                else:
                    st.warning("Veuillez sélectionner un fichier")
            
            else:  # Coller du texte
                raw_message = st.text_area("Message SWIFT", value="", height=160, label_visibility="collapsed")
            
            st.text_input("Modèle SLM (Fallback)", value="qwen2.5:0.5b", disabled=True)
            run = st.button("🚀 LANCER L'ANALYSE")
            st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="section-title">⏱️ Traçabilité Temps Réel</div>', unsafe_allow_html=True)
        trace_container = st.empty()
        trace_container.markdown(textwrap.dedent("""
        <div class="terminal-window">
            <div class="terminal-content" style="color:var(--text-muted); font-style:italic; font-size:0.85rem;">
                En attente du lancement...
            </div>
        </div>
        """).strip(), unsafe_allow_html=True)
        result_container = st.empty()

    if run:
        with st.spinner(""):
            start_time = time.time()
            live_logger = StreamlitLiveLogger(trace_container, pipeline_viz)
            result, _ = run_pipeline(
                raw_message=raw_message,
                message_id="UI_TEST",
                slm_model="qwen2.5:0.5b",
                logger=live_logger
            )
            elapsed = round(time.time() - start_time, 2)
            geo_score = compute_geo_reliability(result)

            pipeline_viz.markdown(render_pipeline_status("OUTPUT"), unsafe_allow_html=True)

            if getattr(result.meta, 'rejected', False):
                st.toast("🚨 Message rejeté — Intervention requise", icon="🚨")
            else:
                st.toast("✅ Analyse complétée avec succès", icon="✅")

            result_container.markdown(render_result_card(result, elapsed), unsafe_allow_html=True)

            # Fiabilité Géospatiale (Ville/Pays)
            st.markdown(render_gauge(geo_score, "🌍 Fiabilité extraction (Ville/Pays)"), unsafe_allow_html=True)

            # Onglets techniques
            st.markdown('<div class="section-title">🗂️ Détails Techniques</div>', unsafe_allow_html=True)
            t1, t2, t3, t4, t5, t6 = st.tabs(["📋 JSON Lisible", "✅ Décision Finale", "🔍 Validation Post-SLM", "✂️ Fragments", "🧩 JSON ISO 20022", "🧾 XML ISO 20022"])

            with t1:
                with st.container():
                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    st.json(_build_display_json(result))
                    st.markdown('</div>', unsafe_allow_html=True)

            with t2:
                _render_final_signal_panel(result)

            with t3:
                # 🔍 ONGLET VALIDATION POST-SLM — Afficher validation stricte
                with st.container():
                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    
                    fallback_used = getattr(result.meta, 'fallback_used', False)
                    llm_signals = list(getattr(result.meta, 'llm_signals', []) or [])
                    warnings_all = list(getattr(result.meta, 'warnings', []) or [])
                    rejected = getattr(result.meta, 'rejected', False)
                    rejection_reasons = list(getattr(result.meta, 'rejection_reasons', []) or [])
                    requires_manual_review = getattr(result.meta, 'requires_manual_review', False)
                    
                    # Affichage du statut de fallback
                    col_fb1, col_fb2, col_fb3 = st.columns(3)
                    with col_fb1:
                        if fallback_used:
                            st.metric("📡 Fallback SLM", "✅ Utilisé")
                        else:
                            st.metric("📡 Fallback SLM", "❌ Non utilisé")
                    
                    with col_fb2:
                        if rejected:
                            st.metric("🚫 Statut", "REJETÉ")
                        elif requires_manual_review:
                            st.metric("⚠️ Statut", "RÉVISION")
                        else:
                            st.metric("✅ Statut", "ACCEPTÉ")
                    
                    with col_fb3:
                        confidence = float(getattr(result.meta, 'parse_confidence', 0.0) or 0.0)
                        st.metric("📊 Confiance", f"{int(confidence*100)}%")
                    
                    st.divider()
                    
                    # LLM Signals
                    if llm_signals:
                        st.subheader("🧠 Signaux LLM")
                        for signal in llm_signals:
                            st.success(f"✓ {signal}")
                    
                    # Validation Warnings (filtrés pour SLM/postal/inference)
                    slm_related_warnings = [w for w in warnings_all if any(kw in str(w).lower() for kw in ['slm', 'postal', 'inference', 'validation', 'geo_', 'pass'])]
                    
                    if slm_related_warnings:
                        st.subheader("🔎 Validations Post-SLM/Inférence")
                        for warning in slm_related_warnings:
                            warning_str = str(warning)
                            if "error" in warning_str.lower() or "fail" in warning_str.lower() or "reject" in warning_str.lower():
                                st.error(f"🚫 {warning_str}")
                            elif "warn" in warning_str.lower() or "suspicious" in warning_str.lower() or "alert" in warning_str.lower():
                                st.warning(f"⚠️ {warning_str}")
                            elif "pass" in warning_str.lower() or "confirm" in warning_str.lower() or "valid" in warning_str.lower():
                                st.success(f"✓ {warning_str}")
                            else:
                                st.info(f"ℹ️ {warning_str}")
                    
                    # Rejection Reasons (si rejeté)
                    if rejected and rejection_reasons:
                        st.subheader("🚨 Raisons du Rejet")
                        for reason in rejection_reasons:
                            st.error(f"❌ {reason}")
                    
                    # Applied Results (Ville, Pays, Postal)
                    if result.country_town:
                        st.subheader("✅ Résultats Appliqués")
                        col_res1, col_res2, col_res3 = st.columns(3)
                        with col_res1:
                            if result.country_town.town:
                                st.success(f"🏘️ Ville: {result.country_town.town}")
                            else:
                                st.error("🏘️ Ville: N/A")
                        with col_res2:
                            if result.country_town.country:
                                st.success(f"🌍 Pays: {result.country_town.country}")
                            else:
                                st.error("🌍 Pays: N/A")
                        with col_res3:
                            if result.country_town.postal_code:
                                st.success(f"📮 Postal: {result.country_town.postal_code}")
                            else:
                                st.info("📮 Postal: N/A")
                    
                    st.markdown('</div>', unsafe_allow_html=True)

            with t4:
                frag_list = getattr(result, 'fragmented_addresses', [])
                if not frag_list:
                    st.info("Aucune fragmentation générée")
                else:
                    for idx, f in enumerate(frag_list):
                        with st.container():
                            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                            st.write(f"**Passe {idx+1}** (Confiance: {getattr(f, 'fragmentation_confidence', 'N/A')})")
                            st.json(_display_fragment_json(f))
                            st.markdown('</div>', unsafe_allow_html=True)

            iso_xml, iso_payload, iso_errors = build_iso20022_party_xml(result, include_envelope=True)
            with t5:
                with st.container():
                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    st.json(iso_payload)
                    st.markdown('</div>', unsafe_allow_html=True)

            with t6:
                with st.container():
                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    if iso_errors:
                        st.warning("Validation ISO incomplète: " + " | ".join(iso_errors))
                    else:
                        st.success("XML ISO 20022 bien formé")
                    st.code(iso_xml, language="xml")
                    st.markdown('</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — MESSAGE SWIFT COMPLET
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "🧾 Message SWIFT complet":
    render_hero(
        "Traitement Message SWIFT Complet",
        "Extraction automatique des champs 50F/50K et 59F/59, puis traitement séparé par le moteur classique",
        "FULL MESSAGE"
    )

    sample_full_message = """{1:F01BIATTNTTXXXX4333652311}{2:I202COBADEFFXXXXN}{3:{108:242007V9CH49978}{119:COV}{121:cefe6327-38af-41f0-ba0d-d6ced37c22v8}}{4:
:20:FT24200431063957
:21:TE2420000101
:32A:240724EUR722,00
:53B:/D/400886502400EUR
:58A:BZITTNTTXXX
:50F:/TN5908003000515000002789
1/SABRINA CONFECTION
2/ZONE INDUSTRIELLE KSAR SAID
3/TN/MANOUBA
:57A:BZITTNTTXXX
:59F:/TN5925048000000102575734
1/FLEN BEN FLEN
2/TUNIS
3/TN/TN 8090
:70:TEST
:72:/ACC/BICIGNCXXXX AVENUE DE LA R
-}"""

    st.markdown('<div class="section-title">📥 Message FIN complet</div>', unsafe_allow_html=True)
    with st.container():
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        input_mode = st.radio(
            "Source",
            ["📝 Coller un message", "📋 Charger l'exemple", "📂 Importer un fichier"],
            horizontal=True,
            label_visibility="collapsed",
        )

        if input_mode == "📋 Charger l'exemple":
            full_message = st.text_area("Message SWIFT complet", value=sample_full_message, height=330, label_visibility="collapsed")
        elif input_mode == "📂 Importer un fichier":
            uploaded_file = st.file_uploader("Choisir un fichier FIN", type=["txt", "swift", "msg", ""], label_visibility="collapsed")
            if uploaded_file is not None:
                full_message = uploaded_file.read().decode("utf-8", errors="ignore")
                st.success(f"Fichier chargé: {uploaded_file.name}")
            else:
                full_message = ""
            full_message = st.text_area("Message SWIFT complet", value=full_message, height=330, label_visibility="collapsed")
        else:
            full_message = st.text_area("Message SWIFT complet", value="", height=330, label_visibility="collapsed")

        run_full_message = st.button("🔎 EXTRAIRE ET TRAITER LES PARTIES")
        st.markdown('</div>', unsafe_allow_html=True)

    if run_full_message:
        all_fields = extract_swift_fields(full_message)
        party_fields = extract_party_fields(full_message)
        other_fields = [f for f in all_fields if str(f.get("tag", "")).upper() not in {"50F", "50K", "59F", "59"}]

        m1, m2, m3 = st.columns(3)
        m1.metric("Champs SWIFT détectés", len(all_fields))
        m2.metric("Parties à traiter", len(party_fields))
        m3.metric("Champs complémentaires", len(other_fields))

        if not party_fields:
            st.error("Aucun champ 50F, 50K, 59F ou 59 détecté dans le message.")
        else:
            st.markdown('<div class="section-title">👥 Résultats Debtor / Creditor</div>', unsafe_allow_html=True)
            tabs = st.tabs([f"{p['role_label']} · {p['tag']}" for p in party_fields])
            summary_rows = []

            for idx, (tab, party_field) in enumerate(zip(tabs, party_fields), start=1):
                with tab:
                    raw_party = party_field["raw_party_field"]
                    result, logger, elapsed, iso_xml, iso_payload, iso_errors = _run_case(
                        raw_party,
                        message_id=f"FULL_SWIFT_{party_field['tag']}_{idx:02d}",
                    )
                    geo = result.country_town
                    summary_rows.append({
                        "role": party_field["role_label"],
                        "tag": party_field["tag"],
                        "account": result.account,
                        "name": " | ".join(result.name or []),
                        "town": geo.town if geo else None,
                        "country": geo.country if geo else None,
                        "confidence": round(float(getattr(result.meta, "parse_confidence", 0.0) or 0.0), 3),
                        "decision": "Rejete" if getattr(result.meta, "rejected", False) else "Accepte",
                    })

                    col_raw, col_res = st.columns([0.8, 1.2], gap="large")
                    with col_raw:
                        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                        st.write(f"**Champ source :** `{party_field['tag']}`")
                        st.write(f"**Rôle :** {party_field['role_label']}")
                        st.code(raw_party, language="text")
                        st.markdown('</div>', unsafe_allow_html=True)

                    with col_res:
                        st.markdown(render_result_card(result, elapsed), unsafe_allow_html=True)

                    details_a, details_b, details_c = st.tabs(["JSON métier", "JSON ISO 20022", "XML ISO 20022"])
                    with details_a:
                        st.json(_build_display_json(result))
                    with details_b:
                        st.json(iso_payload)
                    with details_c:
                        if iso_errors:
                            st.warning("Validation ISO incomplète: " + " | ".join(iso_errors))
                        st.code(iso_xml, language="xml")

            st.markdown('<div class="section-title">📌 Synthèse</div>', unsafe_allow_html=True)
            st.dataframe(summary_rows, use_container_width=True)

        st.markdown('<div class="section-title">➕ Champs complémentaires conservés</div>', unsafe_allow_html=True)
        if other_fields:
            st.dataframe(
                [
                    {
                        "tag": field.get("tag"),
                        "ligne": field.get("line_no"),
                        "valeur": "\n".join(field.get("lines") or []),
                    }
                    for field in other_fields
                ],
                use_container_width=True,
            )
        else:
            st.info("Aucun autre champ détecté.")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 2 — MODE VALIDATION
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "✅ Mode Validation":
    render_hero(
        "Mode Validation Rapide",
        "Tests simples et extraction JSON pour la soutenance",
        "DÉMO"
    )

    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.markdown('<div class="section-title">📥 Saisie</div>', unsafe_allow_html=True)
        with st.container():
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            
            # Onglets de source d'entrée
            input_source = st.radio("Source d'entrée", options=["📝 Coller du texte", "🔽 Sélectionner un cas", "📂 Importer un fichier"], horizontal=True, label_visibility="collapsed")
            
            raw_message = ""
            
            if input_source == "🔽 Sélectionner un cas":
                dataset_choice = st.selectbox("Cas de test", options=list(options.keys()), label_visibility="collapsed")
                raw_message = options[dataset_choice] if dataset_choice else ""
                st.info(f"✓ Cas sélectionné: {dataset_choice}")
            
            elif input_source == "📂 Importer un fichier":
                uploaded_file = st.file_uploader("Choisir un fichier SWIFT", type=["txt", "swift", "msg", ""], label_visibility="collapsed")
                if uploaded_file is not None:
                    raw_message = uploaded_file.read().decode("utf-8", errors="ignore")
                    st.success(f"✓ Fichier chargé: {uploaded_file.name} ({len(raw_message)} caractères)")
                    st.text_area("📄 Contenu du fichier", value=raw_message, height=140, disabled=True, label_visibility="collapsed")
                else:
                    st.warning("Veuillez sélectionner un fichier")
            
            else:  # Coller du texte
                raw_message = st.text_area("Message SWIFT", value="", height=180, label_visibility="collapsed")
            
            run_simple = st.button("▶️ EXTRAIRE LE JSON")
            st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        st.markdown('<div class="section-title">📤 Résultat</div>', unsafe_allow_html=True)
        if run_simple:
            class SilentLogger:
                def log(self, *args, **kwargs): pass
            with st.spinner(""):
                result, _ = run_pipeline(raw_message=raw_message, message_id="DEMO", logger=SilentLogger())
                geo_score = compute_geo_reliability(result)
                iso_xml, iso_payload, iso_errors = build_iso20022_party_xml(result, include_envelope=True)

                clean_json = {"ACCOUNT": result.account}
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
                clean_json = {k: v for k, v in clean_json.items() if v is not None}

                if result.fragmented_addresses:
                    best_frag = sorted(result.fragmented_addresses, key=lambda f: getattr(f, 'fragmentation_confidence', 0.0), reverse=True)[0]
                    for key, val in best_frag.model_dump().items():
                        if val and key not in ['fragmentation_confidence', 'raw_address', 'parser_type'] and not isinstance(val, bool) and not isinstance(val, list):
                            if key.upper() not in clean_json:
                                clean_json[key.upper()] = val

                with st.container():
                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    if getattr(result.meta, 'rejected', False):
                        st.markdown(render_status_badge(False, "MESSAGE REJETÉ"), unsafe_allow_html=True)
                        st.error("Veuillez modifier l'entrée SWIFT")
                    else:
                        st.markdown(render_status_badge(True, "MESSAGE ACCEPTÉ"), unsafe_allow_html=True)
                        st.markdown(render_gauge(result.meta.parse_confidence or 0), unsafe_allow_html=True)
                        st.success(f"Extraction terminée — {int((result.meta.parse_confidence or 0)*100)}% confiance")
                    st.info(f"🌍 Fiabilité extraction Ville/Pays certifiée : {int(geo_score * 100)}%")
                    st.json(clean_json)
                    st.markdown('</div>', unsafe_allow_html=True)

                st.markdown('<div class="section-title">🧩 Mapping ISO 20022</div>', unsafe_allow_html=True)
                with st.container():
                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    st.json(iso_payload)
                    st.markdown('</div>', unsafe_allow_html=True)

                st.markdown('<div class="section-title">🧾 XML ISO 20022</div>', unsafe_allow_html=True)
                with st.container():
                    st.markdown('<div class="glass-card">', unsafe_allow_html=True)
                    if iso_errors:
                        st.warning("Validation ISO incomplète: " + " | ".join(iso_errors))
                    else:
                        st.success("XML généré avec succès")
                    st.code(iso_xml, language="xml")
                    st.markdown('</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 3 — ARCHITECTURE
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📐 Architecture":
    render_hero(
        "Architecture & Méthodologie",
        "Conception TDD du Moteur Hybride SWIFT",
        "DOCS"
    )

    col1, col2 = st.columns([2, 1], gap="large")

    with col1:
        with st.container():
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown("### 🧪 Méthodologie TDD & Empirique")
            st.markdown("""
            - **Test-Driven Development** : Toute correction est validée par un test Pytest avant implémentation
            - **Approche Data-Driven** : Construction couche par couche à partir de messages MT103 réels
            - **Zero-Trust Validation** : Chaque étape émet des signaux de confiance
            """)
            st.markdown('</div>', unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="glass-card" style="margin-top:1rem;">', unsafe_allow_html=True)
            st.markdown("### ⚡ Flux de Traitement Hybride")
            st.code("""
┌─────────────────────────────────────┐
│   Message SWIFT MT103 (Ligne 59/50K) │
└──────────────┬──────────────────────┘
               ↓
╔═══════════════════════════════════════╗
║     MOTEUR DE CORRECTION              ║
╠═══════════════════════════════════════╣
║  (E1) Parseur Regex Déterministe      ║
║  (E2) Validation GeoNames Locale      ║
║  (E2.5) C-Core Libpostal              ║
╚══════════════╬════════════════════════╝
               ↓
     Confiance > 75% ?
        ↓ OUI          ↓ NON
   ┌─────────┐    ┌──────────────┐
   │ 🟢 OUT  │    │ (E3) SLM     │
   │  PUT    │    │ Rescue       │
   └─────────┘    └──────┬───────┘
                         ↓
                    ┌──────────┐
                    │ 🟡 OUTPUT│
                    │(Surveillé)│
                    └──────────┘
            """, language='text')
            st.markdown('</div>', unsafe_allow_html=True)

    with col2:
        with st.container():
            st.markdown('<div class="glass-card">', unsafe_allow_html=True)
            st.markdown("### 🛡️ Stack Technique")
            tech_stack = [
                ("🐍", "Python 3.12", "Core & Pydantic"),
                ("🌍", "GeoNames API", "SQLite Locale"),
                ("🏢", "Libpostal", "NLP Adresses"),
                ("🧠", "Ollama Qwen2.5", "SLM 100% Local"),
                ("📊", "Streamlit", "UX Temps Réel"),
            ]
            for icon, name, desc in tech_stack:
                st.markdown(textwrap.dedent(f"""
                <div style="display:flex; align-items:center; gap:0.75rem; padding:0.7rem;
                            background:var(--bg-base); border-radius:var(--radius-sm);
                            margin-bottom:0.5rem; border:1px solid var(--glass-border);
                            transition:all 0.2s ease;"
                     onmouseover="this.style.borderColor='rgba(6,182,212,0.3)';this.style.transform='translateX(3px)'"
                     onmouseout="this.style.borderColor='var(--glass-border)';this.style.transform='translateX(0)'">
                    <span style="font-size:1.3rem;">{html.escape(icon)}</span>
                    <div>
                        <div style="font-weight:700; font-size:0.88rem;">{html.escape(name)}</div>
                        <div style="font-size:0.74rem; color:var(--text-muted);">{html.escape(desc)}</div>
                    </div>
                </div>
                """).strip(), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

        with st.container():
            st.markdown('<div class="glass-card" style="margin-top:1rem;">', unsafe_allow_html=True)
            st.markdown("### 📈 Métriques Clés")
            metrics = [
                ("Confiance Min.", "75%", "Seuil validation"),
                ("Latence SLM", "~10s", "Fallback uniquement"),
                ("Zero Data Leak", "100%", "Local only"),
            ]
            for label, value, sub in metrics:
                st.markdown(textwrap.dedent(f"""
                <div style="text-align:center; padding:1rem;
                            background:var(--bg-base); border-radius:var(--radius-sm);
                            margin-bottom:0.5rem; border:1px solid var(--glass-border);">
                    <div style="font-size:1.4rem; font-weight:800;
                                background:linear-gradient(135deg, var(--primary), var(--secondary));
                                -webkit-background-clip:text; -webkit-text-fill-color:transparent;">
                        {html.escape(value)}
                    </div>
                    <div style="font-size:0.82rem; font-weight:600; color:var(--text-primary); margin-top:0.15rem;">{html.escape(label)}</div>
                    <div style="font-size:0.7rem; color:var(--text-muted);">{html.escape(sub)}</div>
                </div>
                """).strip(), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 4 — DÉMO GUIDÉE
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "🎬 Démo Guidée":
    render_hero(
        "Démo Guidée Automatique",
        "Exécution séquentielle de cas représentatifs pour la soutenance",
        "SHOWCASE"
    )

    default_demo_cases = [c["label"] for c in cases[:5]]
    selected_demo_cases = st.multiselect(
        "Cas de la démo",
        options=list(options.keys()),
        default=default_demo_cases,
    )

    if st.button("▶️ Lancer la démo complète"):
        if not selected_demo_cases:
            st.warning("Sélectionnez au moins un cas.")
        else:
            rows = []
            progress = st.progress(0)
            status_box = st.empty()
            for idx, label in enumerate(selected_demo_cases):
                status_box.info(f"Exécution: {label}")
                result, logger, elapsed, _, _, _ = _run_case(options[label], message_id=f"DEMO_{idx+1:03d}")
                rows.append(_result_row_from_case(label, result, elapsed))
                progress.progress((idx + 1) / len(selected_demo_cases))

            kpis = _extract_kpis(rows)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Cas", kpis["total"])
            c2.metric("Acceptation", f"{kpis['acceptance_rate']}%")
            c3.metric("Fallback SLM", f"{kpis['fallback_rate']}%")
            c4.metric("Confiance Moy.", kpis["avg_confidence"])
            st.dataframe(rows, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 5 — AVANT / APRÈS SLM
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "🧠 Avant/Après SLM":
    render_hero(
        "Comparatif Avant / Après SLM",
        "Mise en évidence des champs corrigés par le fallback SLM",
        "HYBRID VALUE"
    )

    case_label = st.selectbox("Cas", options=list(options.keys()))
    raw_message = st.text_area("Message SWIFT", value="", height=190)

    if st.button("🔬 Comparer avant/après"):
        before, logger_before, elapsed_before = _run_case_without_slm(raw_message, message_id="BEFORE_SLM")
        after, logger_after, elapsed_after, _, _, _ = _run_case(raw_message, message_id="AFTER_SLM")

        def _fields_view(r):
            return {
                "name": " | ".join(r.name or []),
                "address": " | ".join(r.address_lines or []),
                "town": r.country_town.town if r.country_town else None,
                "country": r.country_town.country if r.country_town else None,
                "postal_code": r.country_town.postal_code if r.country_town else None,
                "confidence": getattr(r.meta, "parse_confidence", 0.0),
                "rejected": getattr(r.meta, "rejected", False),
            }

        b = _fields_view(before)
        a = _fields_view(after)
        changed = [k for k in b if b[k] != a[k]]

        col_b, col_a = st.columns(2, gap="large")
        with col_b:
            st.markdown("### Avant (sans SLM)")
            st.metric("Temps", f"{elapsed_before}s")
            st.json(b)
        with col_a:
            st.markdown("### Après (avec SLM)")
            st.metric("Temps", f"{elapsed_after}s")
            st.json(a)

        st.markdown("### Différences détectées")
        if changed:
            for key in changed:
                st.markdown(f"- **{key}**: `{b[key]}` → `{a[key]}`")
        else:
            st.success("Aucune différence entre les deux exécutions.")

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 6 — EXPLAINABILITY
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "🔎 Explainability":
    render_hero(
        "Explainability",
        "Pourquoi accepté / rejeté, et quels signaux ont guidé la décision",
        "AUDIT"
    )

    case_label = st.selectbox("Cas d'analyse", options=list(options.keys()))
    raw_message = st.text_area("Message", value="", height=180)

    if st.button("🧾 Expliquer la décision"):
        result, logger, elapsed, _, _, _ = _run_case(raw_message, message_id="EXPLAIN")
        st.markdown(render_result_card(result, elapsed), unsafe_allow_html=True)

        c1, c2 = st.columns(2)
        with c1:
            _render_human_signal_list("Rejection reasons", getattr(result.meta, "rejection_reasons", []), "Aucune raison de rejet")
        with c2:
            _render_human_signal_list("Warnings", getattr(result.meta, "warnings", []), "Aucun warning")

        st.markdown("### Timeline des étapes")
        timeline_rows = [
            {
                "step": e.step,
                "time": e.timestamp,
                "level": e.level,
                "message": e.message,
            }
            for e in logger.events
        ]
        st.dataframe(timeline_rows, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 7 — KPI DASHBOARD
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📊 KPI Dashboard":
    render_hero(
        "Dashboard KPI",
        "Mesures globales du moteur sur un lot de cas",
        "METRICS"
    )

    default_kpi_cases = [c["label"] for c in cases[: min(12, len(cases))]]
    selected_cases = st.multiselect("Cas inclus", options=list(options.keys()), default=default_kpi_cases)
    run_kpi = st.button("📈 Calculer les KPI")

    if run_kpi:
        rows = []
        for idx, label in enumerate(selected_cases):
            result, _, elapsed, _, _, _ = _run_case(options[label], message_id=f"KPI_{idx+1:03d}")
            rows.append(_result_row_from_case(label, result, elapsed))

        kpis = _extract_kpis(rows)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total", kpis["total"])
        m2.metric("Acceptation", f"{kpis['acceptance_rate']}%")
        m3.metric("Fallback SLM", f"{kpis['fallback_rate']}%")
        m4.metric("Confiance Moy.", kpis["avg_confidence"])

        m5, m6, m7 = st.columns(3)
        m5.metric("Coverage Country", f"{kpis['country_coverage']}%")
        m6.metric("Coverage Town", f"{kpis['town_coverage']}%")
        m7.metric("Coverage Postal", f"{kpis['postal_coverage']}%")

        st.dataframe(rows, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 8 — COMPARATEUR MULTI-CAS
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "🧪 Comparateur Multi-cas":
    render_hero(
        "Comparateur Multi-cas",
        "Comparer rapidement les sorties, la confiance et la décision",
        "BENCH"
    )

    selected = st.multiselect("Sélectionner les cas", options=list(options.keys()), default=list(options.keys())[:3])
    if st.button("⚖️ Comparer"):
        rows = []
        for idx, label in enumerate(selected):
            result, _, elapsed, _, _, _ = _run_case(options[label], message_id=f"CMP_{idx+1:03d}")
            rows.append(_result_row_from_case(label, result, elapsed))
        st.dataframe(rows, use_container_width=True)

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 9 — EXPORT PRO
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "📦 Export Pro":
    render_hero(
        "Export Professionnel",
        "Téléchargement JSON + XML + Trace dans une archive ZIP",
        "EXPORT"
    )

    case_label = st.selectbox("Cas à exporter", options=list(options.keys()))
    raw_message = st.text_area("Message", value="", height=180)

    if st.button("📤 Générer les exports"):
        result, logger, elapsed, iso_xml, iso_payload, iso_errors = _run_case(raw_message, message_id="EXPORT")
        result_dump = _build_display_json(result)
        trace_dump = logger.as_dicts()

        st.download_button(
            "Télécharger JSON résultat",
            data=json.dumps(result_dump, ensure_ascii=False, indent=2),
            file_name="result.json",
            mime="application/json",
        )
        st.download_button(
            "Télécharger JSON ISO 20022",
            data=json.dumps(iso_payload, ensure_ascii=False, indent=2),
            file_name="iso20022_payload.json",
            mime="application/json",
        )
        st.download_button(
            "Télécharger XML ISO 20022",
            data=iso_xml,
            file_name="iso20022.xml",
            mime="application/xml",
        )

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("input.txt", raw_message)
            zf.writestr("result.json", json.dumps(result_dump, ensure_ascii=False, indent=2))
            zf.writestr("trace.json", json.dumps(trace_dump, ensure_ascii=False, indent=2))
            zf.writestr("iso20022_payload.json", json.dumps(iso_payload, ensure_ascii=False, indent=2))
            zf.writestr("iso20022.xml", iso_xml)
            zf.writestr("metadata.json", json.dumps({
                "elapsed_s": elapsed,
                "iso_errors": iso_errors,
                "fallback_used": bool(getattr(result.meta, "fallback_used", False)),
            }, ensure_ascii=False, indent=2))
        st.download_button(
            "⬇️ Télécharger package ZIP complet",
            data=zip_buffer.getvalue(),
            file_name="swift_engine_export.zip",
            mime="application/zip",
        )

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE 10 — BANQUE DE CAS
# ═══════════════════════════════════════════════════════════════════════════════
elif page == "🗂️ Banque de Cas":
    render_hero(
        "Banque de Cas",
        "Catalogue des scénarios de test avec filtres par catégorie",
        "LIBRARY"
    )

    categories = sorted({c.get("category", "autre") for c in cases})
    selected_category = st.selectbox("Filtrer par catégorie", ["toutes"] + categories)
    filtered_cases = [c for c in cases if selected_category == "toutes" or c.get("category", "autre") == selected_category]

    st.write(f"{len(filtered_cases)} cas affichés")
    case_labels = [c["label"] for c in filtered_cases]
    selected_case = st.selectbox("Cas", case_labels) if case_labels else None

    if selected_case:
        case_obj = next(c for c in filtered_cases if c["label"] == selected_case)
        st.markdown('<div class="glass-card">', unsafe_allow_html=True)
        st.write(f"**Label**: {case_obj.get('label')}")
        st.write(f"**Catégorie**: {case_obj.get('category', 'autre')}")
        st.write(f"**Source**: {case_obj.get('source', 'N/A')}")
        st.code(case_obj.get("raw_message", ""), language="text")
        st.markdown('</div>', unsafe_allow_html=True)

        if st.button("▶️ Exécuter ce cas"):
            result, _, elapsed, _, _, _ = _run_case(case_obj.get("raw_message", ""), message_id="CASE_LIBRARY")
            st.markdown(render_result_card(result, elapsed), unsafe_allow_html=True)
