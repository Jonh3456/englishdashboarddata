"""CSS customizado para deixar o Streamlit tão colorido quanto o protótipo HTML."""

CUSTOM_CSS = """
<style>
/* ---------- Fonte e fundo geral ---------- */
html, body, [class*="css"] { font-family: 'Inter', 'Segoe UI', sans-serif; }
.main .block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1300px; }

/* ---------- Sidebar escura estilo "English Journey" ---------- */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
}
section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
section[data-testid="stSidebar"] .stRadio > label { font-weight: 700; }
section[data-testid="stSidebar"] hr { border-color: #334155; }

/* ---------- Tela de login ---------- */
.login-card {
    max-width: 420px; margin: 40px auto; background: white; border-radius: 24px;
    padding: 36px; box-shadow: 0 12px 30px rgba(0,0,0,0.10); text-align: center;
}
.login-card h1 { font-size: 26px; font-weight: 900; margin-bottom: 4px; }
.login-card p { color: #64748b; margin-bottom: 18px; }

/* ---------- Cards de KPI coloridos ---------- */
.kpi-card {
    border-radius: 22px;
    padding: 20px;
    color: white;
    box-shadow: 0 6px 18px rgba(0,0,0,0.12);
    min-height: 132px;
}
.kpi-card .kpi-icon { font-size: 26px; }
.kpi-card .kpi-label { font-size: 13px; opacity: 0.92; margin-top: 6px; }
.kpi-card .kpi-value { font-size: 30px; font-weight: 900; margin: 2px 0; }
.kpi-card .kpi-sub { font-size: 12px; opacity: 0.85; }

.bg-blue    { background: linear-gradient(135deg, #2563eb, #1d4ed8); }
.bg-violet  { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }
.bg-orange  { background: linear-gradient(135deg, #f97316, #ea580c); }
.bg-emerald { background: linear-gradient(135deg, #10b981, #059669); }
.bg-red     { background: linear-gradient(135deg, #ef4444, #dc2626); }
.bg-teal    { background: linear-gradient(135deg, #14b8a6, #0d9488); }

/* ---------- Banner de missão / gradiente ---------- */
.mission-card {
    border-radius: 24px;
    padding: 26px;
    background: linear-gradient(135deg, #1d4ed8, #7c3aed);
    color: white;
    box-shadow: 0 10px 24px rgba(29,78,216,0.25);
}
.mission-card h2 { margin: 4px 0 0 0; font-size: 26px; font-weight: 900; }
.mission-card p { margin: 0; opacity: 0.9; }

/* ---------- Barra de progresso customizada ---------- */
.progress-track {
    height: 10px; border-radius: 999px; background: rgba(255,255,255,0.25); overflow: hidden; margin-top: 12px;
}
.progress-fill { height: 100%; background: white; border-radius: 999px; }
.progress-track-light { height: 8px; border-radius: 999px; background: #e2e8f0; overflow: hidden; }
.progress-fill-blue { height: 100%; background: #2563eb; border-radius: 999px; }

/* ---------- Cartão de conquista ---------- */
.badge-card {
    border-radius: 20px; padding: 18px; border: 1px solid #e2e8f0; background: white;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.badge-card.unlocked { background: linear-gradient(135deg,#fef3c7,#fde68a); border-color: #f59e0b; }
.badge-icon {
    width: 46px; height: 46px; border-radius: 14px; display: flex; align-items: center; justify-content: center;
    font-size: 20px; background: #f1f5f9; color: #94a3b8;
}
.badge-icon.on { background: #f59e0b; color: white; }

/* ---------- Pódio da competição ---------- */
.podium-card {
    border-radius: 20px; padding: 18px; text-align: center; color: white; box-shadow: 0 8px 18px rgba(0,0,0,0.15);
}

/* ---------- Calendário / próximos estudos ---------- */
.next-card {
    border-radius: 18px; padding: 16px; border: 1px solid #e2e8f0; background: white;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04); display: flex; align-items: center; gap: 14px;
}
.next-card.today { border-color: #2563eb; background: #eff6ff; }
.next-card.overdue { border-color: #f87171; background: #fef2f2; }
.next-date-badge {
    min-width: 58px; text-align: center; border-radius: 14px; padding: 8px 6px;
    background: #f1f5f9; font-weight: 800; color: #334155; line-height: 1.1;
}
.next-date-badge.today { background: #2563eb; color: white; }
.next-date-badge.overdue { background: #ef4444; color: white; }
.day-cell-done { background: linear-gradient(135deg,#10b981,#059669) !important; color: white !important; }
.day-cell-partial { background: linear-gradient(135deg,#fde68a,#fbbf24) !important; }
.day-cell-today { border: 2px solid #2563eb !important; }

/* ---------- Botões primários mais arredondados ---------- */
.stButton>button { border-radius: 12px; font-weight: 700; }
.stDownloadButton>button { border-radius: 12px; font-weight: 700; }
.stForm button { border-radius: 12px; font-weight: 700; }

/* ---------- Tabs ---------- */
button[data-baseweb="tab"] { font-weight: 700; }
</style>
"""
