"""
English Journey — Dashboard interativo de estudo de inglês (6 meses)
Roda no Streamlit, salva os dados em um arquivo Excel versionado no GitHub,
suporta login por usuário/PIN, competição entre pessoas/equipes, calendário
com foco nos próximos estudos, e na Visão Geral separa Pendentes/Concluídas
com botão de nova atividade.
"""
from datetime import date, datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st

import data_model as dm
import github_sync
from theme import CUSTOM_CSS

st.set_page_config(page_title="English Journey — Dashboard", page_icon="🎓", layout="wide")
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ============================================================
# INICIALIZAÇÃO DE DADOS
# ============================================================

def get_today() -> date:
    t = date.today()
    if t < dm.START_DATE:
        return dm.START_DATE
    if t > dm.END_DATE:
        return dm.END_DATE
    return t


def init_data():
    if "dfs" in st.session_state:
        return
    github_mode = github_sync.is_configured()
    st.session_state.github_mode = github_mode
    st.session_state.save_error = None
    st.session_state.last_saved = None

    if github_mode:
        try:
            content, sha = github_sync.fetch_file()
        except Exception as exc:  # noqa: BLE001
            st.session_state.save_error = str(exc)
            content, sha = None, None
        if content:
            raw = dm.bytes_to_workbook(content)
            atividades = dm.normalize_atividades(raw.get("Atividades", dm.empty_atividades_df()))
            usuarios = dm.normalize_usuarios(raw.get("Usuarios", dm.default_usuarios_df()))
        else:
            usuarios = dm.default_usuarios_df()
            atividades = dm.build_template_activities(usuarios.iloc[0]["Usuario"], 1)
            sha = None
        st.session_state.dfs_sha = sha
    else:
        usuarios = dm.default_usuarios_df()
        atividades = dm.build_template_activities(usuarios.iloc[0]["Usuario"], 1)
        st.session_state.dfs_sha = None

    st.session_state.dfs = {"Atividades": atividades, "Usuarios": usuarios}


def persist(message: str = "Atualização do dashboard de inglês"):
    if st.session_state.get("github_mode"):
        try:
            content = dm.workbook_to_bytes(st.session_state.dfs)
            new_sha = github_sync.push_file(content, st.session_state.dfs_sha, message)
            st.session_state.dfs_sha = new_sha
            st.session_state.save_error = None
            st.session_state.last_saved = datetime.now()
        except Exception as exc:  # noqa: BLE001
            st.session_state.save_error = str(exc)
    else:
        st.session_state.last_saved = datetime.now()


def pull_latest():
    if not st.session_state.get("github_mode"):
        return
    try:
        content, sha = github_sync.fetch_file()
        if content:
            raw = dm.bytes_to_workbook(content)
            st.session_state.dfs = {
                "Atividades": dm.normalize_atividades(raw.get("Atividades", dm.empty_atividades_df())),
                "Usuarios": dm.normalize_usuarios(raw.get("Usuarios", dm.default_usuarios_df())),
            }
            st.session_state.dfs_sha = sha
            st.session_state.save_error = None
    except Exception as exc:  # noqa: BLE001
        st.session_state.save_error = str(exc)


init_data()
TODAY = get_today()

# ============================================================
# LOGIN (usuário + senha/PIN)
# ============================================================

def do_login(nome: str, pin: str) -> tuple[bool, str]:
    usuarios = st.session_state.dfs["Usuarios"]
    row = usuarios[usuarios["Usuario"] == nome]
    if row.empty:
        return False, "Usuário não encontrado."
    senha_hash_salva = row.iloc[0]["SenhaHash"]
    if not senha_hash_salva:
        if not pin:
            return False, "Defina um PIN para continuar (primeiro acesso)."
        idx = usuarios.index[usuarios["Usuario"] == nome][0]
        usuarios.at[idx, "SenhaHash"] = dm.hash_password(pin)
        st.session_state.dfs["Usuarios"] = usuarios
        persist(f"Definir PIN inicial de {nome}")
        return True, ""
    if dm.hash_password(pin) == senha_hash_salva:
        return True, ""
    return False, "PIN incorreto."


def login_screen():
    usuarios = st.session_state.dfs["Usuarios"]
    st.markdown(
        """<div class="login-card">
                <h1>🎓 English Journey</h1>
                <p>Entre para acompanhar sua evolução no inglês</p>
            </div>""",
        unsafe_allow_html=True,
    )
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        with st.form("login_form"):
            nomes = usuarios["Usuario"].tolist()
            nome_sel = st.selectbox("Quem é você?", nomes) if nomes else None
            tem_senha = False
            if nome_sel:
                row = usuarios[usuarios["Usuario"] == nome_sel]
                tem_senha = bool(row.iloc[0]["SenhaHash"]) if not row.empty else False
            label_pin = "PIN (4+ dígitos ou senha)" if tem_senha else "Crie um PIN (primeiro acesso)"
            pin = st.text_input(label_pin, type="password")
            entrar = st.form_submit_button("Entrar", use_container_width=True)
            if entrar:
                if not nome_sel:
                    st.error("Cadastre um usuário primeiro (peça para o administrador).")
                else:
                    ok, msg = do_login(nome_sel, pin)
                    if ok:
                        st.session_state.auth_user = nome_sel
                        st.rerun()
                    else:
                        st.error(msg)
        with st.expander("➕ Sou novo(a) aqui — criar meu usuário"):
            st.caption("Ao criar seu usuário, seu cronograma completo de 6 meses é gerado automaticamente.")
            with st.form("novo_usuario_login_form"):
                novo_nome = st.text_input("Seu nome")
                nova_equipe = st.text_input("Equipe", value="Time Fluência")
                novo_pin = st.text_input("Crie um PIN", type="password")
                criar = st.form_submit_button("Criar usuário e entrar", use_container_width=True)
                if criar:
                    if not novo_nome.strip() or not novo_pin:
                        st.error("Informe nome e PIN.")
                    elif novo_nome in usuarios["Usuario"].tolist():
                        st.error("Já existe alguém com esse nome. Escolha outro ou faça login acima.")
                    else:
                        cor = dm.USER_PALETTE[len(usuarios) % len(dm.USER_PALETTE)]
                        novo = pd.DataFrame([{
                            "Usuario": novo_nome, "Equipe": nova_equipe, "Cor": cor,
                            "MetaSemanal": 14, "SenhaHash": dm.hash_password(novo_pin),
                        }])
                        st.session_state.dfs["Usuarios"] = pd.concat([usuarios, novo], ignore_index=True)
                        atividades = st.session_state.dfs["Atividades"]
                        max_id = int(atividades["ID"].max()) if len(atividades) else 0
                        plano = dm.build_template_activities(novo_nome, max_id + 1)
                        st.session_state.dfs["Atividades"] = pd.concat([atividades, plano], ignore_index=True)
                        persist(f"Criar novo usuário: {novo_nome}")
                        st.session_state.auth_user = novo_nome
                        st.session_state.flash_new_user_count = len(plano)
                        st.rerun()


if "auth_user" not in st.session_state:
    st.session_state.auth_user = None

if st.session_state.auth_user is None:
    login_screen()
    st.stop()

current_user = st.session_state.auth_user
atividades: pd.DataFrame = st.session_state.dfs["Atividades"]
usuarios: pd.DataFrame = st.session_state.dfs["Usuarios"]

# ============================================================
# HELPERS DE CÁLCULO
# ============================================================

def week_bounds(d: date):
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start, end


def compute_stats(user: str) -> dict:
    df = atividades[atividades["Usuario"] == user].copy()
    if df.empty:
        return dict(
            actual_hours=0.0, planned_hours=0.0, xp=0, level=1, stars=0,
            completion_rate=0.0, streak=0, week_hours=0.0, weekly_goal=14,
            completed=df, week_df=df,
        )
    df["minutos_reais"] = df.apply(
        lambda r: r["MinutosExecutados"] if r["Concluido"] and r["MinutosExecutados"] > 0
        else (r["MinutosPlanejados"] if r["Concluido"] else 0), axis=1
    )
    completed = df[df["Concluido"]]
    actual_hours = completed["minutos_reais"].sum() / 60
    planned_hours = df["MinutosPlanejados"].sum() / 60
    xp = round(completed["minutos_reais"].sum() / 5)
    level = xp // 500 + 1
    stars = min(5, xp // 1000)
    completion_rate = (len(completed) / len(df) * 100) if len(df) else 0.0

    ws, we = week_bounds(TODAY)
    df["data_dt"] = pd.to_datetime(df["Data"], errors="coerce").dt.date
    week_df = df[(df["data_dt"] >= ws) & (df["data_dt"] <= we)]
    week_hours = week_df[week_df["Concluido"]]["minutos_reais"].sum() / 60

    dates_done = sorted(set(completed["Data"]), reverse=True)
    streak = 0
    if dates_done:
        streak = 1
        prev = datetime.strptime(dates_done[0], "%Y-%m-%d").date()
        for ds in dates_done[1:]:
            cur = datetime.strptime(ds, "%Y-%m-%d").date()
            if (prev - cur).days == 1:
                streak += 1
                prev = cur
            else:
                break

    weekly_goal = 14
    urow = usuarios[usuarios["Usuario"] == user]
    if len(urow):
        weekly_goal = int(urow.iloc[0]["MetaSemanal"])

    return dict(
        actual_hours=actual_hours, planned_hours=planned_hours, xp=xp, level=level,
        stars=stars, completion_rate=completion_rate, streak=streak, week_hours=week_hours,
        weekly_goal=weekly_goal, completed=completed, week_df=week_df,
    )


def kpi_card(col, icon, label, value, sub, css_class):
    col.markdown(
        f"""<div class="kpi-card {css_class}">
                <div class="kpi-icon">{icon}</div>
                <div class="kpi-label">{label}</div>
                <div class="kpi-value">{value}</div>
                <div class="kpi-sub">{sub}</div>
            </div>""",
        unsafe_allow_html=True,
    )


def toggle_activity(activity_id: int):
    idx = atividades.index[atividades["ID"] == activity_id]
    if len(idx) == 0:
        return
    i = idx[0]
    new_val = not bool(atividades.at[i, "Concluido"])
    atividades.at[i, "Concluido"] = new_val
    if new_val:
        if not atividades.at[i, "MinutosExecutados"]:
            atividades.at[i, "MinutosExecutados"] = atividades.at[i, "MinutosPlanejados"]
        atividades.at[i, "DataConclusao"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    else:
        atividades.at[i, "DataConclusao"] = ""
    st.session_state.dfs["Atividades"] = atividades
    persist(f"Marcar atividade {activity_id} como {'concluída' if new_val else 'pendente'}")


def add_activity(user: str, data_str: str, horario: str, tarefa: str, habilidade: str,
                  modalidade: str, minutos: int):
    max_id = int(atividades["ID"].max()) if len(atividades) else 0
    nova = pd.DataFrame([{
        "ID": max_id + 1, "Usuario": user, "Data": data_str, "Horario": horario,
        "Tarefa": tarefa, "Habilidade": habilidade, "Modalidade": modalidade,
        "MinutosPlanejados": minutos, "MinutosExecutados": 0, "Concluido": False,
        "Anotacoes": "", "DataConclusao": "",
    }])
    st.session_state.dfs["Atividades"] = pd.concat([atividades, nova], ignore_index=True)
    persist(f"Adicionar atividade: {tarefa} ({user})")


# ============================================================
# SIDEBAR — NAVEGAÇÃO, USUÁRIO LOGADO, STATUS DO GITHUB
# ============================================================
with st.sidebar:
    st.markdown("### 🎓 English Journey")
    st.caption("Plano de 6 meses • 31/ago/2026 a 28/fev/2027")
    st.divider()

    st.markdown(f"**👤 {current_user}**")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state.auth_user = None
        st.rerun()

    st.divider()
    page = st.radio(
        "Navegação",
        ["🎯 Visão geral", "📅 Calendário", "📊 Evolução", "🏆 Competição", "🥇 Conquistas", "⚙️ Configurações"],
        label_visibility="collapsed",
    )

    st.divider()
    if st.session_state.get("github_mode"):
        st.success("🔗 Conectado ao GitHub")
        if st.session_state.get("last_saved"):
            st.caption(f"Último salvamento: {st.session_state.last_saved.strftime('%d/%m %H:%M')}")
        if st.button("🔄 Buscar atualizações da equipe", use_container_width=True):
            pull_latest()
            st.rerun()
    else:
        st.warning("⚠️ GitHub não configurado — dados salvos apenas nesta sessão local.")
    if st.session_state.get("save_error"):
        st.error(f"Erro ao sincronizar: {st.session_state.save_error}")

stats = compute_stats(current_user)

# ============================================================
# CABEÇALHO
# ============================================================
if st.session_state.get("flash_new_user_count"):
    st.success(
        f"✅ Cronograma criado automaticamente para **{current_user}**: "
        f"{st.session_state.flash_new_user_count} atividades geradas para os 6 meses "
        f"({dm.START_DATE.strftime('%d/%m/%Y')} a {dm.END_DATE.strftime('%d/%m/%Y')})."
    )
    st.session_state.flash_new_user_count = None

header_left, header_right = st.columns([3, 1])
with header_left:
    st.markdown(
        f"<p style='color:#2563eb;font-weight:800;letter-spacing:1px;text-transform:uppercase;font-size:13px;'>"
        f"31 de agosto de 2026 a 28 de fevereiro de 2027 • {current_user}</p>",
        unsafe_allow_html=True,
    )
    st.markdown("## Sua evolução no inglês")
    st.caption("Consistência hoje, fluência amanhã.")
with header_right:
    st.write("")
    st.write("")
    if st.button("➕ Nova atividade", use_container_width=True, type="primary"):
        st.session_state.show_new_activity_form = not st.session_state.get("show_new_activity_form", False)

if st.session_state.get("show_new_activity_form"):
    with st.container():
        st.markdown('<div class="new-activity-card">', unsafe_allow_html=True)
        with st.form("nova_atividade_geral"):
            st.markdown("##### ➕ Adicionar nova atividade")
            c1, c2 = st.columns(2)
            nova_data = c1.date_input("Data", value=TODAY, min_value=dm.START_DATE, max_value=dm.END_DATE)
            novo_horario = c2.text_input("Horário", value="18:00")
            nova_tarefa = st.text_input("Tarefa")
            c3, c4, c5 = st.columns(3)
            nova_habilidade = c3.selectbox("Habilidade", dm.SKILLS)
            nova_modalidade = c4.selectbox("Modalidade", dm.MODALITIES)
            novos_minutos = c5.number_input("Minutos", min_value=5, step=5, value=30)
            col_ok, col_cancel = st.columns(2)
            salvar_nova = col_ok.form_submit_button("💾 Salvar", use_container_width=True, type="primary")
            cancelar_nova = col_cancel.form_submit_button("Cancelar", use_container_width=True)
            if salvar_nova:
                if not nova_tarefa.strip():
                    st.error("Informe o nome da tarefa.")
                else:
                    add_activity(current_user, nova_data.isoformat(), novo_horario, nova_tarefa,
                                 nova_habilidade, nova_modalidade, novos_minutos)
                    st.session_state.show_new_activity_form = False
                    st.success("Atividade adicionada!")
                    st.rerun()
            if cancelar_nova:
                st.session_state.show_new_activity_form = False
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# PÁGINA: VISÃO GERAL
# ============================================================
if page == "🎯 Visão geral":
    c1, c2, c3, c4 = st.columns(4)
    kpi_card(c1, "⏱️", "Horas executadas", f"{stats['actual_hours']:.1f}h", f"{stats['week_hours']:.1f}h nesta semana", "bg-blue")
    kpi_card(c2, "⭐", "Pontos e nível", f"{stats['xp']} XP", f"Nível {stats['level']} • {stats['stars']}/5 estrelas", "bg-violet")
    kpi_card(c3, "🔥", "Sequência atual", f"{stats['streak']} dias", "Continue para não perder a sequência", "bg-orange")
    kpi_card(c4, "✅", "Taxa de conclusão", f"{stats['completion_rate']:.0f}%", f"{len(stats['completed'])} tarefas concluídas", "bg-emerald")

    st.write("")
    left, right = st.columns([2, 1])

    with left:
        st.markdown("#### Plano desta semana")
        week_df = stats["week_df"].sort_values(["Data", "Horario"])
        pct = min(100, (stats["week_hours"] / stats["weekly_goal"] * 100) if stats["weekly_goal"] else 0)
        st.markdown(
            f"<div class='progress-track-light'><div class='progress-fill-blue' style='width:{pct}%;'></div></div>"
            f"<p style='text-align:right;font-size:12px;color:#64748b;'>{stats['week_hours']:.1f} / {stats['weekly_goal']}h</p>",
            unsafe_allow_html=True,
        )

        pendentes = week_df[~week_df["Concluido"]]
        concluidas = week_df[week_df["Concluido"]]

        st.markdown(f'<p class="section-label">🔲 Pendentes ({len(pendentes)})</p>', unsafe_allow_html=True)
        if pendentes.empty:
            st.caption("Nenhuma pendência esta semana. 🎉")
        for _, row in pendentes.iterrows():
            cols = st.columns([0.06, 0.7, 0.24])
            cols[0].checkbox("Concluído", value=False, key=f"chk_{row['ID']}", on_change=toggle_activity,
                              args=(row["ID"],), label_visibility="collapsed")
            cols[1].markdown(
                f"<span style='font-weight:700;'>{row['Tarefa']}</span><br>"
                f"<span style='font-size:12px;color:#64748b;'>{row['Data']} • {row['Horario']} • {row['MinutosPlanejados']} min • {row['Habilidade']} • {row['Modalidade']}</span>",
                unsafe_allow_html=True,
            )
            with cols[2].popover("✏️ Editar"):
                novos_min = st.number_input("Minutos executados", min_value=0, step=5, value=int(row["MinutosExecutados"]), key=f"min_{row['ID']}")
                notas = st.text_area("Anotações", value=row["Anotacoes"], key=f"notas_{row['ID']}")
                if st.button("Salvar", key=f"save_{row['ID']}"):
                    idx = atividades.index[atividades["ID"] == row["ID"]][0]
                    atividades.at[idx, "MinutosExecutados"] = novos_min
                    atividades.at[idx, "Anotacoes"] = notas
                    st.session_state.dfs["Atividades"] = atividades
                    persist("Editar atividade")
                    st.rerun()

        st.markdown(f'<p class="section-label">✅ Concluídas ({len(concluidas)})</p>', unsafe_allow_html=True)
        if concluidas.empty:
            st.caption("Ainda não há atividades concluídas nesta semana.")
        for _, row in concluidas.iterrows():
            cols = st.columns([0.06, 0.94])
            cols[0].checkbox("Concluído", value=True, key=f"chk_{row['ID']}", on_change=toggle_activity,
                              args=(row["ID"],), label_visibility="collapsed")
            cols[1].markdown(
                f"<div class='task-row done'><span style='text-decoration:line-through;color:#64748b;'>{row['Tarefa']}</span><br>"
                f"<span style='font-size:12px;color:#94a3b8;'>{row['Data']} • {row['Horario']} • {row['Habilidade']} • concluída em {row['DataConclusao'] or '—'}</span></div>",
                unsafe_allow_html=True,
            )

    with right:
        pct_week = min(100, (stats["week_hours"] / stats["weekly_goal"] * 100) if stats["weekly_goal"] else 0)
        st.markdown(
            f"""<div class="mission-card">
                    <p>🎯 Missão semanal</p>
                    <h2>Atingir {stats['weekly_goal']} horas</h2>
                    <div class="progress-track">
                        <div class="progress-fill" style="width:{pct_week}%;"></div>
                    </div>
                    <p style="margin-top:10px;">{stats['week_hours']:.1f}h realizadas •
                        {max(0, stats['weekly_goal']-stats['week_hours']):.1f}h restantes</p>
                    <p style="margin-top:14px;font-size:13px;">🎁 Recompensa: 2 estrelas e 250 XP bônus</p>
                </div>""",
            unsafe_allow_html=True,
        )
        st.write("")
        st.markdown("##### Equilíbrio de habilidades")
        skill_data = stats["completed"].groupby("Habilidade")["minutos_reais"].sum().reset_index()
        if not skill_data.empty:
            skill_data["Horas"] = (skill_data["minutos_reais"] / 60).round(1)
        if skill_data.empty or skill_data["Horas"].sum() == 0:
            st.info("Marque atividades como concluídas para ver o gráfico.")
        else:
            chart = alt.Chart(skill_data).mark_arc(innerRadius=60).encode(
                theta="Horas:Q",
                color=alt.Color("Habilidade:N", scale=alt.Scale(domain=list(dm.SKILL_COLORS.keys()), range=list(dm.SKILL_COLORS.values())), legend=alt.Legend(orient="bottom")),
                tooltip=["Habilidade", "Horas"],
            ).properties(height=260)
            st.altair_chart(chart, use_container_width=True)

# ============================================================
# PÁGINA: CALENDÁRIO (próximos estudos + heatmap + grid mensal)
# ============================================================
elif page == "📅 Calendário":
    df_user = atividades[atividades["Usuario"] == current_user].copy()
    df_user["data_dt"] = pd.to_datetime(df_user["Data"], errors="coerce").dt.date

    st.markdown("#### 🔜 Próximos estudos")
    proximos = df_user[(~df_user["Concluido"]) & (df_user["data_dt"] >= TODAY)].sort_values(["data_dt", "Horario"]).head(6)
    atrasadas = df_user[(~df_user["Concluido"]) & (df_user["data_dt"] < TODAY)].sort_values(["data_dt", "Horario"])

    if len(atrasadas):
        st.markdown(f"⚠️ **{len(atrasadas)} atividade(s) atrasada(s)**")
        with st.expander("Ver atividades atrasadas"):
            for _, row in atrasadas.iterrows():
                cc = st.columns([0.08, 0.92])
                cc[0].checkbox("Concluído", value=False, key=f"chk_atraso_{row['ID']}",
                               on_change=toggle_activity, args=(row["ID"],), label_visibility="collapsed")
                cc[1].markdown(f"**{row['Tarefa']}** — {row['data_dt'].strftime('%d/%m')} • {row['Habilidade']}")

    if proximos.empty:
        st.info("Nenhuma atividade pendente nos próximos dias. 🎉")
    else:
        for _, row in proximos.iterrows():
            is_today = row["data_dt"] == TODAY
            badge_cls = "today" if is_today else ""
            dia_label = "HOJE" if is_today else row["data_dt"].strftime("%d/%m")
            mes_label = "" if is_today else row["data_dt"].strftime("%b").upper()
            cA, cB = st.columns([0.08, 0.92])
            cA.checkbox("Concluído", value=False, key=f"chk_next_{row['ID']}",
                        on_change=toggle_activity, args=(row["ID"],), label_visibility="collapsed")
            with cB:
                st.markdown(
                    f"""<div class="next-card {badge_cls}">
                            <div class="next-date-badge {badge_cls}">{dia_label}<br><small>{mes_label}</small></div>
                            <div><b>{row['Tarefa']}</b><br>
                                <span style="font-size:12px;color:#64748b;">{row['Horario']} • {row['MinutosPlanejados']} min • {row['Habilidade']} • {row['Modalidade']}</span>
                            </div>
                        </div>""",
                    unsafe_allow_html=True,
                )
            st.write("")

    st.divider()
    st.markdown("#### 🔥 Seu progresso ao longo dos 6 meses")
    heat = df_user.groupby("data_dt").agg(total=("ID", "count"), feitas=("Concluido", "sum")).reset_index()
    all_days = pd.DataFrame({"data_dt": pd.date_range(dm.START_DATE, dm.END_DATE).date})
    heat = all_days.merge(heat, on="data_dt", how="left").fillna(0)
    heat["data_ts"] = pd.to_datetime(heat["data_dt"])
    heat["semana"] = ((heat["data_ts"] - pd.Timestamp(dm.START_DATE)).dt.days // 7)
    heat["dia_semana"] = heat["data_ts"].dt.strftime("%a")
    heat["ratio"] = heat.apply(lambda r: (r["feitas"] / r["total"]) if r["total"] > 0 else 0, axis=1)
    dias_ordem = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    heat_chart = alt.Chart(heat).mark_rect(cornerRadius=3).encode(
        x=alt.X("semana:O", title="Semana", axis=alt.Axis(labels=False, ticks=False)),
        y=alt.Y("dia_semana:N", sort=dias_ordem, title=""),
        color=alt.Color("ratio:Q", scale=alt.Scale(range=["#e2e8f0", "#10b981"], domain=[0, 1]), legend=None),
        tooltip=[alt.Tooltip("data_dt:T", title="Data"), alt.Tooltip("feitas:Q", title="Concluídas"), alt.Tooltip("total:Q", title="Total")],
    ).properties(height=180)
    st.altair_chart(heat_chart, use_container_width=True)

    st.divider()
    months = pd.date_range(dm.START_DATE, dm.END_DATE, freq="MS").to_list()
    if not months or months[0].date() > dm.START_DATE:
        months = [pd.Timestamp(dm.START_DATE)] + months
    month_labels = [m.strftime("%B/%Y").capitalize() for m in months]
    default_idx = 0
    for i, m in enumerate(months):
        if m.year == TODAY.year and m.month == TODAY.month:
            default_idx = i
            break
    sel_label = st.select_slider("📅 Ver mês", options=month_labels, value=month_labels[default_idx])
    sel_month = months[month_labels.index(sel_label)]

    first_day = sel_month.date()
    first_weekday = first_day.weekday()
    grid_start = first_day - timedelta(days=first_weekday)
    dias_grid = [grid_start + timedelta(days=i) for i in range(42)]

    day_status = {}
    for _, row in df_user.iterrows():
        d = row["data_dt"]
        day_status.setdefault(d, {"total": 0, "feitas": 0})
        day_status[d]["total"] += 1
        if row["Concluido"]:
            day_status[d]["feitas"] += 1

    st.markdown(f"##### {sel_label}")
    dias_semana_lbl = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    header_cols = st.columns(7)
    for hc, lbl in zip(header_cols, dias_semana_lbl):
        hc.markdown(f"<div style='text-align:center;font-weight:800;color:#64748b;font-size:12px;'>{lbl}</div>", unsafe_allow_html=True)

    if "cal_dia_sel" not in st.session_state:
        st.session_state.cal_dia_sel = TODAY

    for w in range(6):
        row_cols = st.columns(7)
        for i in range(7):
            d = dias_grid[w * 7 + i]
            with row_cols[i]:
                fora_mes = d.month != sel_month.month
                status = day_status.get(d, {"total": 0, "feitas": 0})
                total, feitas = status["total"], status["feitas"]
                label = f"{d.day}"
                if total:
                    label += f" • {int(feitas)}/{int(total)}"
                disabled = d < dm.START_DATE or d > dm.END_DATE or fora_mes
                btn_type = "primary" if d == st.session_state.cal_dia_sel else "secondary"
                if st.button(label, key=f"cal_{d.isoformat()}", type=btn_type, disabled=disabled, use_container_width=True):
                    st.session_state.cal_dia_sel = d
                    st.rerun()
                if total and feitas == total and not disabled:
                    st.markdown("<div style='text-align:center;font-size:11px;color:#059669;'>✅ completo</div>", unsafe_allow_html=True)
                elif feitas > 0 and not disabled:
                    st.markdown("<div style='text-align:center;font-size:11px;color:#b45309;'>🟡 parcial</div>", unsafe_allow_html=True)

    st.divider()
    dia_sel = st.session_state.cal_dia_sel
    st.markdown(f"##### 📌 Atividades de {dia_sel.strftime('%d/%m/%Y')}")
    itens_dia = df_user[df_user["data_dt"] == dia_sel].sort_values("Horario")
    if itens_dia.empty:
        st.info("Nenhuma atividade neste dia.")
    for _, row in itens_dia.iterrows():
        cc = st.columns([0.06, 0.7, 0.24])
        cc[0].checkbox("Concluído", value=bool(row["Concluido"]), key=f"chk_dia_{row['ID']}",
                        on_change=toggle_activity, args=(row["ID"],), label_visibility="collapsed")
        style = "text-decoration:line-through;color:#94a3b8;" if row["Concluido"] else "font-weight:700;"
        cc[1].markdown(f"<span style='{style}'>{row['Tarefa']}</span><br>"
                        f"<span style='font-size:12px;color:#64748b;'>{row['Horario']} • {row['MinutosPlanejados']} min • {row['Habilidade']}</span>",
                        unsafe_allow_html=True)

    with st.expander("➕ Adicionar atividade neste dia"):
        with st.form(f"nova_atividade_{dia_sel.isoformat()}"):
            nc1, nc2 = st.columns(2)
            tarefa = nc1.text_input("Tarefa")
            horario = nc2.text_input("Horário", value="18:00")
            nc3, nc4 = st.columns(2)
            habilidade = nc3.selectbox("Habilidade", dm.SKILLS)
            modalidade = nc4.selectbox("Modalidade", dm.MODALITIES)
            minutos = st.number_input("Minutos planejados", min_value=5, step=5, value=30)
            adicionar = st.form_submit_button("Adicionar")
            if adicionar and tarefa.strip():
                add_activity(current_user, dia_sel.isoformat(), horario, tarefa, habilidade, modalidade, minutos)
                st.success("Atividade adicionada!")
                st.rerun()

# ============================================================
# PÁGINA: EVOLUÇÃO
# ============================================================
elif page == "📊 Evolução":
    f1, f2, f3 = st.columns(3)
    skill_f = f1.selectbox("Habilidade", ["Todas"] + dm.SKILLS)
    mod_f = f2.selectbox("Modalidade", ["Todas"] + dm.MODALITIES)
    status_f = f3.selectbox("Status", ["Todos", "Concluídos", "Pendentes"])

    df = atividades[atividades["Usuario"] == current_user].copy()
    if skill_f != "Todas":
        df = df[df["Habilidade"] == skill_f]
    if mod_f != "Todas":
        df = df[df["Modalidade"] == mod_f]
    if status_f == "Concluídos":
        df = df[df["Concluido"]]
    elif status_f == "Pendentes":
        df = df[~df["Concluido"]]

    df["data_dt"] = pd.to_datetime(df["Data"], errors="coerce")
    df["minutos_reais"] = df.apply(lambda r: (r["MinutosExecutados"] or r["MinutosPlanejados"]) if r["Concluido"] else 0, axis=1)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Horas nas últimas 8 semanas")
        weeks = []
        for i in range(8):
            wstart = dm.START_DATE + timedelta(days=7 * i)
            wend = wstart + timedelta(days=6)
            sub = df[(df["data_dt"].dt.date >= wstart) & (df["data_dt"].dt.date <= wend)]
            weeks.append({"Semana": f"S{i+1}", "Horas": round(sub["minutos_reais"].sum() / 60, 1), "Tipo": "Executado"})
            weeks.append({"Semana": f"S{i+1}", "Horas": stats["weekly_goal"], "Tipo": "Meta"})
        wdf = pd.DataFrame(weeks)
        chart = alt.Chart(wdf).mark_bar().encode(
            x=alt.X("Semana:N"), y=alt.Y("Horas:Q"),
            color=alt.Color("Tipo:N", scale=alt.Scale(domain=["Executado", "Meta"], range=["#2563eb", "#cbd5e1"])),
            xOffset="Tipo:N", tooltip=["Semana", "Tipo", "Horas"],
        ).properties(height=300)
        st.altair_chart(chart, use_container_width=True)

    with col2:
        st.markdown("##### Evolução mensal")
        month_rows = []
        cursor = pd.Timestamp(dm.START_DATE)
        for _ in range(6):
            mend = cursor + pd.offsets.MonthEnd(0)
            sub = df[(df["data_dt"] >= cursor) & (df["data_dt"] <= mend)]
            month_rows.append({"Mes": cursor.strftime("%b/%y"), "Horas": round(sub["minutos_reais"].sum() / 60, 1)})
            cursor = cursor + pd.offsets.MonthBegin(1)
        mdf = pd.DataFrame(month_rows)
        line = alt.Chart(mdf).mark_area(line={"color": "#8b5cf6", "strokeWidth": 3}, color=alt.Gradient(
            gradient="linear",
            stops=[alt.GradientStop(color="#8b5cf6", offset=0), alt.GradientStop(color="#ffffff", offset=1)],
            x1=1, x2=1, y1=1, y2=0,
        )).encode(x=alt.X("Mes:N", sort=None), y="Horas:Q", tooltip=["Mes", "Horas"]).properties(height=300)
        st.altair_chart(line, use_container_width=True)

# ============================================================
# PÁGINA: COMPETIÇÃO (EQUIPES)
# ============================================================
elif page == "🏆 Competição":
    st.markdown("#### Ranking geral")
    rows = []
    for _, u in usuarios.iterrows():
        s = compute_stats(u["Usuario"])
        rows.append({
            "Usuario": u["Usuario"], "Equipe": u["Equipe"], "Cor": u["Cor"],
            "XP": s["xp"], "Horas": round(s["actual_hours"], 1), "Sequencia": s["streak"], "Estrelas": s["stars"],
        })
    rank_df = pd.DataFrame(rows).sort_values("XP", ascending=False).reset_index(drop=True)

    medalhas = ["🥇", "🥈", "🥉"]
    cols = st.columns(min(3, max(1, len(rank_df))))
    for i, (_, r) in enumerate(rank_df.head(3).iterrows()):
        with cols[i]:
            st.markdown(
                f"""<div class="podium-card" style="background:{r['Cor']};">
                        <div style="font-size:34px;">{medalhas[i] if i < 3 else '🎖️'}</div>
                        <div style="font-size:20px;font-weight:900;margin-top:6px;">{r['Usuario']}</div>
                        <div style="font-size:13px;opacity:.9;">{r['Equipe']}</div>
                        <div style="font-size:26px;font-weight:900;margin-top:10px;">{r['XP']} XP</div>
                        <div style="font-size:12px;opacity:.9;">{r['Horas']}h • {'⭐'*int(r['Estrelas']) or '—'}</div>
                    </div>""",
                unsafe_allow_html=True,
            )

    st.write("")
    st.markdown("##### Comparativo de XP entre todos")
    bar = alt.Chart(rank_df).mark_bar(cornerRadiusEnd=8).encode(
        x=alt.X("XP:Q"), y=alt.Y("Usuario:N", sort="-x"),
        color=alt.Color("Usuario:N", scale=alt.Scale(domain=rank_df["Usuario"].tolist(), range=rank_df["Cor"].tolist()), legend=None),
        tooltip=["Usuario", "Equipe", "XP", "Horas"],
    ).properties(height=max(120, 46 * len(rank_df)))
    st.altair_chart(bar, use_container_width=True)

    st.write("")
    st.markdown("##### 🏅 Times")
    team_df = rank_df.groupby("Equipe").agg(XP=("XP", "sum"), Horas=("Horas", "sum"), Integrantes=("Usuario", "count")).reset_index().sort_values("XP", ascending=False)
    tcols = st.columns(min(3, max(1, len(team_df))))
    for i, (_, t) in enumerate(team_df.iterrows()):
        with tcols[i % len(tcols)]:
            kpi_card(st, "👥", t["Equipe"], f"{t['XP']} XP", f"{t['Horas']:.1f}h • {t['Integrantes']} pessoa(s)", ["bg-blue", "bg-violet", "bg-teal"][i % 3])

    st.write("")
    st.markdown("##### 📈 Corrida de horas (acumulado desde 31/ago/2026)")
    lines = []
    for _, u in usuarios.iterrows():
        udf = atividades[(atividades["Usuario"] == u["Usuario"]) & (atividades["Concluido"])].copy()
        udf["data_dt"] = pd.to_datetime(udf["Data"], errors="coerce")
        udf["minutos_reais"] = udf.apply(lambda r: r["MinutosExecutados"] or r["MinutosPlanejados"], axis=1)
        daily = udf.groupby("data_dt")["minutos_reais"].sum().sort_index().cumsum() / 60
        for d, v in daily.items():
            lines.append({"Data": d, "HorasAcumuladas": v, "Usuario": u["Usuario"], "Cor": u["Cor"]})
    if lines:
        race_df = pd.DataFrame(lines)
        race_chart = alt.Chart(race_df).mark_line(point=True, strokeWidth=3).encode(
            x="Data:T", y="HorasAcumuladas:Q",
            color=alt.Color("Usuario:N", scale=alt.Scale(domain=usuarios["Usuario"].tolist(), range=usuarios["Cor"].tolist())),
            tooltip=["Usuario", "Data", "HorasAcumuladas"],
        ).properties(height=320)
        st.altair_chart(race_chart, use_container_width=True)
    else:
        st.info("Assim que alguém concluir atividades, a corrida de horas aparece aqui.")

# ============================================================
# PÁGINA: CONQUISTAS
# ============================================================
elif page == "🥇 Conquistas":
    quem = st.selectbox("Ver conquistas de:", usuarios["Usuario"].tolist(), index=usuarios["Usuario"].tolist().index(current_user))
    s = compute_stats(quem)
    completed = s["completed"]
    speaking_done = len(completed[completed["Habilidade"] == "Speaking"]) if len(completed) else 0
    listening_hours = (completed[completed["Habilidade"] == "Listening"]["minutos_reais"].sum() / 60) if len(completed) else 0
    dias_unicos = completed["Data"].nunique() if len(completed) else 0

    st.markdown(
        f"""<div class="mission-card" style="background:linear-gradient(135deg,#f59e0b,#ea580c);">
                <p>🏅 Nível de {quem}</p>
                <h2>Nível {s['level']}: Explorador do Inglês</h2>
                <p style="margin-top:8px;">{s['xp']} XP acumulados • {s['stars']}/5 estrelas</p>
            </div>""",
        unsafe_allow_html=True,
    )
    st.progress(min(1.0, (s["xp"] % 500) / 500), text=f"{500 - (s['xp'] % 500)} XP para o próximo nível")
    st.write("")

    achievements = [
        ("Primeiros passos", "Concluir a primeira atividade", len(completed) >= 1, "+50 XP"),
        ("Semana consistente", "Estudar em 7 dias diferentes", dias_unicos >= 7, "⭐ 1 estrela"),
        ("Falante corajoso", "Completar 10 sessões de Speaking", speaking_done >= 10, "+200 XP"),
        ("Ouvido treinado", "Completar 20 horas de Listening", listening_hours >= 20, "⭐ 1 estrela"),
        ("Meta semanal", "Executar a meta em uma semana", s["week_hours"] >= s["weekly_goal"], "⭐⭐ 2 estrelas"),
        ("Fluency Champion", "Concluir 80% do plano de 6 meses", s["completion_rate"] >= 80, "👑 Troféu final"),
    ]
    cols = st.columns(3)
    for i, (title, desc, ok, reward) in enumerate(achievements):
        with cols[i % 3]:
            st.markdown(
                f"""<div class="badge-card {'unlocked' if ok else ''}">
                        <div class="badge-icon {'on' if ok else ''}">🏆</div>
                        <div style="font-weight:900;margin-top:10px;">{title}</div>
                        <div style="font-size:13px;color:#64748b;margin-top:4px;">{desc}</div>
                        <div style="font-weight:800;color:#f59e0b;margin-top:10px;">{'Desbloqueado ✓' if ok else reward}</div>
                    </div>""",
                unsafe_allow_html=True,
            )
            st.write("")

# ============================================================
# PÁGINA: CONFIGURAÇÕES
# ============================================================
elif page == "⚙️ Configurações":
    st.markdown("#### Metas pessoais")
    urow_idx = usuarios.index[usuarios["Usuario"] == current_user][0]
    novo_goal = st.number_input("Meta semanal de horas", min_value=1, max_value=60, value=int(usuarios.at[urow_idx, "MetaSemanal"]))
    if st.button("Salvar meta"):
        usuarios.at[urow_idx, "MetaSemanal"] = novo_goal
        st.session_state.dfs["Usuarios"] = usuarios
        persist("Atualizar meta semanal")
        st.success("Meta atualizada!")
        st.rerun()

    st.divider()
    st.markdown("#### 🔐 Segurança")
    with st.form("trocar_pin_form"):
        pin_atual = st.text_input("PIN atual", type="password")
        pin_novo = st.text_input("Novo PIN", type="password")
        trocar = st.form_submit_button("Trocar PIN")
        if trocar:
            senha_hash_salva = usuarios.at[urow_idx, "SenhaHash"]
            if senha_hash_salva and dm.hash_password(pin_atual) != senha_hash_salva:
                st.error("PIN atual incorreto.")
            elif not pin_novo:
                st.error("Informe o novo PIN.")
            else:
                usuarios.at[urow_idx, "SenhaHash"] = dm.hash_password(pin_novo)
                st.session_state.dfs["Usuarios"] = usuarios
                persist(f"Trocar PIN de {current_user}")
                st.success("PIN atualizado!")

    st.divider()
    st.markdown("#### 👥 Gerenciar pessoas e equipes")
    st.dataframe(usuarios.drop(columns=["SenhaHash"]), use_container_width=True, hide_index=True)

    with st.form("novo_usuario_form"):
        st.markdown("**Adicionar nova pessoa**")
        st.caption("O cronograma completo de 6 meses é gerado automaticamente para a nova pessoa.")
        nc1, nc2, nc3, nc4 = st.columns(4)
        novo_nome = nc1.text_input("Nome")
        nova_equipe = nc2.text_input("Equipe", value="Time Fluência")
        nova_cor = nc3.color_picker("Cor", value=dm.USER_PALETTE[len(usuarios) % len(dm.USER_PALETTE)])
        nova_meta = nc4.number_input("Meta semanal (h)", min_value=1, max_value=60, value=14)
        submitted = st.form_submit_button("➕ Adicionar pessoa (gera cronograma de 6 meses)", type="primary")
        if submitted:
            if not novo_nome.strip():
                st.error("Informe um nome.")
            elif novo_nome in usuarios["Usuario"].tolist():
                st.error("Já existe uma pessoa com esse nome.")
            else:
                new_user_row = pd.DataFrame([{
                    "Usuario": novo_nome, "Equipe": nova_equipe, "Cor": nova_cor,
                    "MetaSemanal": nova_meta, "SenhaHash": "",
                }])
                st.session_state.dfs["Usuarios"] = pd.concat([usuarios, new_user_row], ignore_index=True)
                max_id = int(atividades["ID"].max()) if len(atividades) else 0
                novo_plano = dm.build_template_activities(novo_nome, max_id + 1)
                st.session_state.dfs["Atividades"] = pd.concat([atividades, novo_plano], ignore_index=True)
                persist(f"Adicionar pessoa: {novo_nome}")
                st.success(f"{novo_nome} adicionado(a)! {len(novo_plano)} atividades geradas para os 6 meses. "
                           f"A pessoa cria o próprio PIN no primeiro login.")
                st.rerun()

    if len(usuarios) > 1:
        with st.expander("🗑️ Remover pessoa"):
            remover = st.selectbox("Selecione", usuarios["Usuario"].tolist(), key="remover_sel")
            if st.button("Remover definitivamente (e todo o plano dela)", type="secondary"):
                st.session_state.dfs["Usuarios"] = usuarios[usuarios["Usuario"] != remover].reset_index(drop=True)
                st.session_state.dfs["Atividades"] = atividades[atividades["Usuario"] != remover].reset_index(drop=True)
                persist(f"Remover pessoa: {remover}")
                if remover == current_user:
                    st.session_state.auth_user = None
                st.rerun()

    st.divider()
    st.markdown("#### 💾 Backup e restauração")
    col_a, col_b = st.columns(2)
    with col_a:
        backup_bytes = dm.workbook_to_bytes(st.session_state.dfs)
        st.download_button("⬇️ Baixar backup (.xlsx)", data=backup_bytes, file_name="estudo_ingles_backup.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
    with col_b:
        if st.button("↺ Restaurar plano padrão de " + current_user, use_container_width=True):
            others = atividades[atividades["Usuario"] != current_user]
            max_id = int(others["ID"].max()) if len(others) else 0
            novo_plano = dm.build_template_activities(current_user, max_id + 1)
            st.session_state.dfs["Atividades"] = pd.concat([others, novo_plano], ignore_index=True)
            persist(f"Restaurar plano padrão de {current_user}")
            st.success("Plano restaurado!")
            st.rerun()

    st.divider()
    st.markdown("#### 🔗 Conexão com o GitHub")
    if st.session_state.get("github_mode"):
        st.success("Conectado — todas as alterações são salvas automaticamente como commits no repositório configurado.")
        with st.expander("🩺 Diagnóstico da conexão"):
            st.json(github_sync.get_diagnostics())
    else:
        st.info(
            "Configure `GITHUB_TOKEN`, `GITHUB_REPO`, `GITHUB_BRANCH` e `GITHUB_FILE_PATH` em "
            "`.streamlit/secrets.toml` (local) ou em *Settings → Secrets* no Streamlit Community Cloud."
        )
        with st.expander("🩺 Diagnóstico da conexão"):
            st.json(github_sync.get_diagnostics())
