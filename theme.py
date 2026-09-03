"""CSS customizado do dashboard."""

CUSTOM_CSS = """
<style>
html, body, [class*="css"] { font-family: 'Inter', 'Segoe UI', sans-serif; }
.main .block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1300px; }

section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0f172a 0%, #111827 100%);
}
section[data-testid="stSidebar"] * { color: #e2e8f0 !important; }

.login-hero { text-align:center; margin-bottom: 20px; }
.login-hero h1 { font-size: 30px; font-weight: 900; margin-bottom: 4px; }
.login-hero p { color: #64748b; }

.admin-badge {
    background:#f59e0b; color:white; font-size:10px; font-weight:800;
    padding:2px 8px; border-radius:999px; margin-left:6px;
}

.kpi-card {
    border-radius: 22px; padding: 20px; color: white;
    box-shadow: 0 6px 18px rgba(0,0,0,0.12); min-height: 132px;
}
.kpi-card .kpi-icon { font-size: 26px; }
.kpi-card .kpi-label { font-size: 13px; opacity: 0.92; margin-top: 6px; }
.kpi-card .kpi-value { font-size: 30px; font-weight: 900; margin: 2px 0; }
.kpi-card .kpi-sub { font-size: 12px; opacity: 0.85; }

.bg-blue    { background: linear-gradient(135deg, #2563eb, #1d4ed8); }
.bg-violet  { background: linear-gradient(135deg, #8b5cf6, #7c3aed); }
.bg-orange  { background: linear-gradient(135deg, #f97316, #ea580c); }
.bg-emerald { background: linear-gradient(135deg, #10b981, #059669); }
.bg-teal    { background: linear-gradient(135deg, #14b8a6, #0d9488); }

.mission-card {
    border-radius: 24px; padding: 26px;
    background: linear-gradient(135deg, #1d4ed8, #7c3aed); color: white;
    box-shadow: 0 10px 24px rgba(29,78,216,0.25);
}
.mission-card h2 { margin: 4px 0 0 0; font-size: 26px; font-weight: 900; }
.mission-card p { margin: 0; opacity: 0.9; }

.progress-track { height: 10px; border-radius: 999px; background: rgba(255,255,255,0.25); overflow: hidden; margin-top: 12px; }
.progress-fill { height: 100%; background: white; border-radius: 999px; }
.progress-track-light { height: 8px; border-radius: 999px; background: #e2e8f0; overflow: hidden; }
.progress-fill-blue { height: 100%; background: #2563eb; border-radius: 999px; }

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

.podium-card {
    border-radius: 20px; padding: 18px; text-align: center; color: white; box-shadow: 0 8px 18px rgba(0,0,0,0.15);
}

.stButton>button { border-radius: 12px; font-weight: 700; }
.stDownloadButton>button { border-radius: 12px; font-weight: 700; }
button[data-baseweb="tab"] { font-weight: 700; }
</style>
"""
