"""CSS customizado para deixar o Streamlit tão colorido quanto o protótipo HTML."""

CUSTOM_CSS = """
<style>
.block-container { padding-top: 2rem; }

/* ---------- KPI cards ---------- */
.kpi-card {
    border-radius: 22px;
    padding: 20px;
    color: white;
    box-shadow: 0 6px 18px rgba(0,0,0,0.08);
    min-height: 120px;
}
.kpi-card.bg-blue    { background: linear-gradient(135deg, #2563eb, #1d4ed8); }
.kpi-card.bg-violet  { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }
.kpi-card.bg-orange  { background: linear-gradient(135deg, #f97316, #ea580c); }
.kpi-card.bg-emerald { background: linear-gradient(135deg, #10b981, #059669); }
.kpi-card.bg-teal    { background: linear-gradient(135deg, #14b8a6, #0d9488); }
.kpi-icon  { font-size: 26px; margin-bottom: 6px; }
.kpi-label { font-size: 13px; opacity: 0.9; }
.kpi-value { font-size: 28px; font-weight: 900; margin: 2px 0; }
.kpi-sub   { font-size: 12px; opacity: 0.85; }

/* ---------- Barras de progresso ---------- */
.progress-track-light {
    width: 100%; height: 10px; border-radius: 999px;
    background: #e2e8f0; overflow: hidden;
}
.progress-fill-blue { height: 100%; background: #2563eb; border-radius: 999px; }

.progress-track {
    width: 100%; height: 12px; border-radius: 999px;
    background: rgba(255,255,255,0.25); overflow: hidden;
}
.progress-fill { height: 100%; background: white; border-radius: 999px; }

/* ---------- Card de missão semanal ---------- */
.mission-card {
    border-radius: 24px; padding: 26px; color: white;
    background: linear-gradient(135deg, #1d4ed8, #7c3aed);
    box-shadow: 0 10px 24px rgba(29,78,216,0.25);
}
.mission-card h2 { margin: 6px 0 14px 0; font-size: 24px; }
.mission-card p  { margin: 0; }

/* ---------- Pódio (Competição) ---------- */
.podium-card {
    border-radius: 22px; padding: 22px; color: white; text-align: center;
    box-shadow: 0 8px 20px rgba(0,0,0,0.12);
}

/* ---------- Badges de conquistas ---------- */
.badge-card {
    border: 1px solid #e2e8f0; border-radius: 20px; padding: 18px;
    background: #f8fafc; text-align: left;
}
.badge-card.unlocked { background: #fff7ed; border-color: #fdba74; }
.badge-icon {
    width: 46px; height: 46px; border-radius: 16px;
    display: flex; align-items: center; justify-content: center;
    font-size: 22px; background: #e2e8f0; color: #94a3b8;
}
.badge-icon.on { background: #f59e0b; color: white; }

/* ---------- Tela de login ---------- */
.login-hero {
    text-align: center; padding: 30px 10px 10px 10px;
}
.login-hero h1 { font-size: 32px; font-weight: 900; margin-bottom: 4px; }
.login-hero p  { color: #64748b; }

/* ---------- Modo Admin ---------- */
.admin-badge {
    display: inline-block; background: #1e293b; color: white; font-size: 11px;
    font-weight: 800; padding: 3px 10px; border-radius: 999px; margin-left: 8px;
}

/* ---------- Botões e diversos ---------- */
div[data-testid="stButton"] button { border-radius: 12px; font-weight: 700; }
</style>
"""
