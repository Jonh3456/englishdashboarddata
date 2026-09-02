"""
English Journey — Dashboard interativo de estudo de inglês (6 meses)
Roda no Streamlit, salva os dados em um arquivo Excel versionado no GitHub,
e suporta competição entre duas (ou mais) pessoas / equipes.

Cada pessoa tem seu próprio plano de 6 meses, que começa no dia em que ela
é cadastrada (não em uma data fixa), e pode ser PERSONALIZADO a partir da
disponibilidade (dias/horários livres) e dos materiais de estudo escolhidos.
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
    """Data real de hoje (sem limitar à janela do usuário 'Você' de exemplo,
    já que agora cada pessoa pode ter sua própria janela de 6 meses)."""
    return date.today()


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
    st.session_state.current_user = usuarios.iloc[0]["Usuario"] if len(usuarios) else None


def persist(message: str = "Atualização do dashboard de inglês"):
    """Salva o estado atual. Se o GitHub estiver configurado, faz commit lá."""
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
    """Busca a versão mais recente do GitHub (ex: alteração feita pelo parceiro de equipe)."""
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
atividades: pd.DataFrame = st.session_state.dfs["Atividades"]
usuarios: pd.DataFrame = st.session_state.dfs["Usuarios"]
TODAY = get_today()

# ============================================================
# HELPERS DE CÁLCULO
# ============================================================

def week_bounds(d: date):
    start = d - timedelta(days=d.weekday())
    end = start + timedelta(days=6)
    return start, end


def user_date_range(user: str) -> tuple[date, date]:
    """Retorna (data mínima, data máxima) das atividades de uma pessoa.
    Usado pelo Calendário para exibir a janela real de cada pessoa
    (que pode começar em dias diferentes, dependendo de quando foi cadastrada)."""
    df = atividades[atividades["Usuario"] == user]
    if df.empty:
        return dm.START_DATE, dm.END_DATE
    datas = pd.to_datetime(df["Data"], errors="coerce").dt.date.dropna()
    if datas.empty:
        return dm.START_DATE, dm.END_DATE
    return datas.min(), datas.max()


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
        else (r["MinutosPlanejados"] if r["Concluido"] else 0), axis=1,
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
    """Marca/desmarca uma atividade. Ao concluir, ela é 'arquivada' — ou seja,
    some das listas de pendências da Visão Geral (mas continua contando para
    XP, estatísticas, calendário e histórico)."""
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


def add_activity(pessoa: str, titulo: str, data_val: date, horario: str, habilidade: str,
                  modalidade: str, minutos: int, notas: str = ""):
    global atividades
    max_id = int(atividades["ID"].max()) if len(atividades) else 0
    nova = pd.DataFrame([{
        "ID": max_id + 1, "Usuario": pessoa, "Data": data_val.isoformat(),
        "Horario": horario, "Tarefa": titulo, "Habilidade": habilidade,
        "Modalidade": modalidade, "MinutosPlanejados": minutos, "MinutosExecutados": 0,
        "Concluido": False, "Anotacoes": notas, "DataConclusao": "",
    }])
    atividades = pd.concat([atividades, nova], ignore_index=True)
    st.session_state.dfs["Atividades"] = atividades
    persist(f"Nova atividade: {titulo} ({pessoa})")


# ============================================================
# SIDEBAR — NAVEGAÇÃO, USUÁRIO, STATUS DO GITHUB
# ============================================================
with st.sidebar:
    st.markdown("### 🎓 English Journey")
    st.caption("Cada pessoa tem seu próprio plano de 6 meses")
    st.divider()

    user_list = usuarios["Usuario"].tolist() if len(usuarios) else []
    if user_list:
        current_user = st.selectbox(
            "👤 Quem está estudando?", user_list,
            index=user_list.index(st.session_state.current_user) if st.session_state.current_user in user_list else 0,
        )
        st.session_state.current_user = current_user
    else:
        current_user = None
        st.info("Cadastre o primeiro usuário em Configurações.")

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
        if st.button("🔄 Buscar atualizações da equipe", width="stretch"):
            pull_latest()
            st.rerun()
    else:
        st.warning("⚠️ GitHub não configurado — dados salvos apenas nesta sessão local.")
        with st.expander("Como conectar ao GitHub"):
            st.markdown(
                "Adicione em `.streamlit/secrets.toml` (ou nas *Secrets* do "
                "Streamlit Community Cloud):\n\n"
                "```toml\nGITHUB_TOKEN = \"ghp_xxx\"\n"
                "GITHUB_REPO = \"usuario/repo\"\n"
                "GITHUB_BRANCH = \"main\"\n"
                "GITHUB_FILE_PATH = \"data/estudo_ingles_dados.xlsx\"\n```"
            )
    if st.session_state.get("save_error"):
        st.error(f"Erro ao sincronizar: {st.session_state.save_error}")

if current_user is None:
    st.stop()

stats = compute_stats(current_user)
user_start, user_end = user_date_range(current_user)

# ============================================================
# CABEÇALHO
# ============================================================
st.markdown(
    f"<p style='color:#2563eb;font-weight:800;letter-spacing:1px;text-transform:uppercase;font-size:13px;'>"
    f"{user_start.strftime('%d/%m/%Y')} a {user_end.strftime('%d/%m/%Y')} • {current_user}</p>",
    unsafe_allow_html=True,
)
st.markdown("## Sua evolução no inglês")
st.caption("Consistência hoje, fluência amanhã.")

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

    # -------- Botão no topo para adicionar nova tarefa --------
    top_l, top_r = st.columns([5, 1.4])
    with top_l:
        st.markdown("#### 📋 Minhas tarefas pendentes")
    with top_r:
        if st.button("➕ Nova atividade", type="primary", width="stretch", key="btn_toggle_form_nova"):
            st.session_state.mostrar_form_nova_tarefa = not st.session_state.get("mostrar_form_nova_tarefa", False)

    if st.session_state.get("mostrar_form_nova_tarefa"):
        with st.container(border=True):
            st.markdown("**➕ Adicionar nova atividade**")
            fc1, fc2, fc3 = st.columns(3)
            novo_titulo = fc1.text_input("Tarefa", key="novo_titulo")
            nova_data = fc2.date_input("Data", value=TODAY, key="nova_data")
            novo_horario = fc3.text_input("Horário (HH:MM)", value="18:00", key="novo_horario")
            fc4, fc5, fc6 = st.columns(3)
            nova_habilidade = fc4.selectbox("Habilidade", dm.SKILLS, key="nova_habilidade")
            nova_modalidade = fc5.selectbox("Modalidade", dm.MODALITIES, key="nova_modalidade")
            novos_minutos = fc6.number_input("Minutos planejados", min_value=5, step=5, value=30, key="novos_minutos")
            novas_notas = st.text_area("Anotações (opcional)", key="novas_notas")
            bcol1, bcol2 = st.columns(2)
            if bcol1.button("💾 Salvar atividade", type="primary", width="stretch", key="btn_salvar_nova"):
                if novo_titulo.strip():
                    add_activity(current_user, novo_titulo, nova_data, novo_horario,
                                 nova_habilidade, nova_modalidade, int(novos_minutos), novas_notas)
                    st.session_state.mostrar_form_nova_tarefa = False
                    st.success("Atividade adicionada!")
                    st.rerun()
                else:
                    st.error("Informe o nome da tarefa.")
            if bcol2.button("✖️ Cancelar", width="stretch", key="btn_cancelar_nova"):
                st.session_state.mostrar_form_nova_tarefa = False
                st.rerun()

    st.write("")
    left, right = st.columns([2, 1])

    with left:
        # -------- Alternância de visualização: por semana ou por dia --------
        modo_visao = st.radio(
            "Ver pendências:", ["📅 Semana", "📆 Dia"], horizontal=True,
            key="modo_visao_pendencias", label_visibility="visible",
        )

        df_pessoa = atividades[atividades["Usuario"] == current_user].copy()
        df_pessoa["data_dt"] = pd.to_datetime(df_pessoa["Data"], errors="coerce").dt.date

        if modo_visao == "📅 Semana":
            if "semana_offset" not in st.session_state:
                st.session_state.semana_offset = 0
            nav1, nav2, nav3 = st.columns([1, 3, 1])
            if nav1.button("◀", key="semana_prev"):
                st.session_state.semana_offset -= 1
            if nav3.button("▶", key="semana_next"):
                st.session_state.semana_offset += 1
            base_day = TODAY + timedelta(weeks=st.session_state.semana_offset)
            ws, we = week_bounds(base_day)
            nav2.markdown(f"<p style='text-align:center;font-weight:700;'>{ws.strftime('%d/%m')} a {we.strftime('%d/%m')}</p>", unsafe_allow_html=True)
            periodo_df = df_pessoa[(df_pessoa["data_dt"] >= ws) & (df_pessoa["data_dt"] <= we)]
            periodo_horas_meta = stats["weekly_goal"]
            periodo_label = "semana"
        else:
            if "dia_offset" not in st.session_state:
                st.session_state.dia_offset = 0
            nav1, nav2, nav3 = st.columns([1, 3, 1])
            if nav1.button("◀", key="dia_prev"):
                st.session_state.dia_offset -= 1
            if nav3.button("▶", key="dia_next"):
                st.session_state.dia_offset += 1
            sel_day = TODAY + timedelta(days=st.session_state.dia_offset)
            nav2.markdown(f"<p style='text-align:center;font-weight:700;'>{sel_day.strftime('%A, %d/%m').capitalize()}</p>", unsafe_allow_html=True)
            periodo_df = df_pessoa[df_pessoa["data_dt"] == sel_day]
            periodo_horas_meta = round(stats["weekly_goal"] / 7, 1)
            periodo_label = "dia"

        periodo_df = periodo_df.sort_values(["Data", "Horario"])
        pendentes_df = periodo_df[~periodo_df["Concluido"]]
        concluidas_periodo_df = periodo_df[periodo_df["Concluido"]]

        horas_feitas_periodo = concluidas_periodo_df.apply(
            lambda r: (r["MinutosExecutados"] or r["MinutosPlanejados"]), axis=1
        ).sum() / 60 if len(concluidas_periodo_df) else 0.0
        pct = min(100, (horas_feitas_periodo / periodo_horas_meta * 100) if periodo_horas_meta else 0)
        st.markdown(
            f"<div class='progress-track-light'><div class='progress-fill-blue' style='width:{pct}%;'></div></div>"
            f"<p style='text-align:right;font-size:12px;color:#64748b;'>{horas_feitas_periodo:.1f} / {periodo_horas_meta}h ({periodo_label})</p>",
            unsafe_allow_html=True,
        )

        if pendentes_df.empty:
            st.success(f"🎉 Nenhuma pendência para {'esta semana' if modo_visao == '📅 Semana' else 'este dia'}! Bom trabalho.")
        for _, row in pendentes_df.iterrows():
            cols = st.columns([0.06, 0.7, 0.24])
            cols[0].checkbox(
                "Concluído", value=False, key=f"chk_{row['ID']}",
                on_change=toggle_activity, args=(row["ID"],), label_visibility="collapsed",
            )
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

        # Atividades concluídas ficam "arquivadas": saem da lista principal,
        # mas continuam disponíveis aqui (recolhido) caso queira revisar ou desmarcar.
        if not concluidas_periodo_df.empty:
            with st.expander(f"✅ Concluídas neste {periodo_label} ({len(concluidas_periodo_df)}) — arquivadas da tela principal"):
                for _, row in concluidas_periodo_df.iterrows():
                    cols = st.columns([0.06, 0.94])
                    cols[0].checkbox(
                        "Concluído", value=True, key=f"chk_done_{row['ID']}",
                        on_change=toggle_activity, args=(row["ID"],), label_visibility="collapsed",
                    )
                    cols[1].markdown(
                        f"<span style='text-decoration:line-through;color:#94a3b8;'>{row['Tarefa']}</span> "
                        f"<span style='font-size:12px;color:#64748b;'>— {row['Data']} • {row['Horario']}</span>",
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
        if len(stats["completed"]):
            skill_data = stats["completed"].groupby("Habilidade")["minutos_reais"].sum().reset_index()
            skill_data["Horas"] = (skill_data["minutos_reais"] / 60).round(1)
        else:
            skill_data = pd.DataFrame(columns=["Habilidade", "minutos_reais", "Horas"])
        if skill_data.empty or skill_data["Horas"].sum() == 0:
            st.info("Marque atividades como concluídas para ver o gráfico.")
        else:
            chart = alt.Chart(skill_data).mark_arc(innerRadius=60).encode(
                theta="Horas:Q",
                color=alt.Color("Habilidade:N", scale=alt.Scale(domain=list(dm.SKILL_COLORS.keys()), range=list(dm.SKILL_COLORS.values())), legend=alt.Legend(orient="bottom")),
                tooltip=["Habilidade", "Horas"],
            ).properties(height=260)
            st.altair_chart(chart, width="stretch")

# ============================================================
# PÁGINA: CALENDÁRIO
# ============================================================
elif page == "📅 Calendário":
    months = pd.date_range(user_start.replace(day=1), user_end, freq="MS").to_list()
    if not months or months[0].date() > user_start:
        months = [pd.Timestamp(user_start.replace(day=1))] + months
    month_labels = [m.strftime("%B/%Y").capitalize() for m in months]
    default_idx = 0
    for i, m in enumerate(months):
        if m.year == TODAY.year and m.month == TODAY.month:
            default_idx = i
            break
    sel_label = st.select_slider("Mês", options=month_labels, value=month_labels[default_idx])
    sel_month = months[month_labels.index(sel_label)]

    st.markdown("##### 🔥 Heatmap de estudo (todo o período)")
    df_user = atividades[atividades["Usuario"] == current_user].copy()
    df_user["data_dt"] = pd.to_datetime(df_user["Data"], errors="coerce")
    heat = df_user.groupby("data_dt").agg(total=("ID", "count"), feitas=("Concluido", "sum")).reset_index()
    all_days = pd.DataFrame({"data_dt": pd.date_range(user_start, user_end)})
    heat = all_days.merge(heat, on="data_dt", how="left").fillna(0)
    heat["semana"] = ((heat["data_dt"] - pd.Timestamp(user_start)).dt.days // 7)
    heat["dia_semana"] = heat["data_dt"].dt.strftime("%a")
    heat["ratio"] = heat.apply(lambda r: (r["feitas"] / r["total"]) if r["total"] > 0 else 0, axis=1)
    dias_ordem = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    heat_chart = alt.Chart(heat).mark_rect(cornerRadius=3).encode(
        x=alt.X("semana:O", title="Semana", axis=alt.Axis(labels=False, ticks=False)),
        y=alt.Y("dia_semana:N", sort=dias_ordem, title=""),
        color=alt.Color("ratio:Q", scale=alt.Scale(scheme="blues", domain=[0, 1]), legend=None),
        tooltip=[alt.Tooltip("data_dt:T", title="Data"), alt.Tooltip("feitas:Q", title="Concluídas"), alt.Tooltip("total:Q", title="Total")],
    ).properties(height=200)
    st.altair_chart(heat_chart, width="stretch")

    st.markdown(f"##### 📝 Atividades de {sel_label}")
    month_start = sel_month.date()
    next_month = (sel_month + pd.offsets.MonthBegin(1)).date()
    mask = (atividades["Usuario"] == current_user) & (pd.to_datetime(atividades["Data"]).dt.date >= month_start) & (pd.to_datetime(atividades["Data"]).dt.date < next_month)
    month_df = atividades[mask].sort_values(["Data", "Horario"]).copy()

    edited = st.data_editor(
        month_df.drop(columns=["ID", "Usuario", "DataConclusao"]),
        num_rows="dynamic",
        width="stretch",
        key=f"editor_{current_user}_{sel_label}",
        column_config={
            "Data": st.column_config.TextColumn("Data (AAAA-MM-DD)"),
            "Horario": st.column_config.TextColumn("Horário"),
            "Habilidade": st.column_config.SelectboxColumn("Habilidade", options=dm.SKILLS),
            "Modalidade": st.column_config.SelectboxColumn("Modalidade", options=dm.MODALITIES),
            "MinutosPlanejados": st.column_config.NumberColumn("Min. planejados", min_value=0, step=5),
            "MinutosExecutados": st.column_config.NumberColumn("Min. executados", min_value=0, step=5),
            "Concluido": st.column_config.CheckboxColumn("Feito?"),
            "Anotacoes": st.column_config.TextColumn("Anotações"),
        },
    )

    if st.button("💾 Salvar alterações deste mês", type="primary"):
        others = atividades[~mask].copy()
        max_id = int(atividades["ID"].max()) if len(atividades) else 0
        new_rows = []
        for _, r in edited.iterrows():
            new_rows.append({
                "ID": max_id + len(new_rows) + 1 if pd.isna(r.get("ID")) else r.get("ID"),
                "Usuario": current_user,
                "Data": str(r["Data"]),
                "Horario": str(r["Horario"]),
                "Tarefa": r["Tarefa"],
                "Habilidade": r["Habilidade"],
                "Modalidade": r["Modalidade"],
                "MinutosPlanejados": int(r["MinutosPlanejados"] or 0),
                "MinutosExecutados": int(r["MinutosExecutados"] or 0),
                "Concluido": bool(r["Concluido"]),
                "Anotacoes": r.get("Anotacoes", "") or "",
                "DataConclusao": datetime.now().strftime("%Y-%m-%d %H:%M") if bool(r["Concluido"]) else "",
            })
        seen_ids = set(others["ID"].tolist())
        next_id = max_id + 1
        for row in new_rows:
            if row["ID"] in seen_ids or not row["ID"]:
                row["ID"] = next_id
                next_id += 1
            seen_ids.add(row["ID"])
        new_month_df = pd.DataFrame(new_rows, columns=dm.ATIVIDADES_COLUMNS)
        st.session_state.dfs["Atividades"] = pd.concat([others, new_month_df], ignore_index=True)
        persist(f"Atualizar atividades de {sel_label} — {current_user}")
        st.success("Alterações salvas!")
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
            wstart = user_start + timedelta(days=7 * i)
            wend = wstart + timedelta(days=6)
            sub = df[(df["data_dt"].dt.date >= wstart) & (df["data_dt"].dt.date <= wend)]
            weeks.append({"Semana": f"S{i+1}", "Horas": round(sub["minutos_reais"].sum() / 60, 1), "Tipo": "Executado"})
            weeks.append({"Semana": f"S{i+1}", "Horas": stats["weekly_goal"], "Tipo": "Meta"})
        wdf = pd.DataFrame(weeks)
        chart = alt.Chart(wdf).mark_bar().encode(
            x=alt.X("Semana:N"),
            y=alt.Y("Horas:Q"),
            color=alt.Color("Tipo:N", scale=alt.Scale(domain=["Executado", "Meta"], range=["#2563eb", "#cbd5e1"])),
            xOffset="Tipo:N",
            tooltip=["Semana", "Tipo", "Horas"],
        ).properties(height=300)
        st.altair_chart(chart, width="stretch")

    with col2:
        st.markdown("##### Evolução mensal")
        month_rows = []
        cursor = pd.Timestamp(user_start)
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
        st.altair_chart(line, width="stretch")

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
        x=alt.X("XP:Q"),
        y=alt.Y("Usuario:N", sort="-x"),
        color=alt.Color("Usuario:N", scale=alt.Scale(domain=rank_df["Usuario"].tolist(), range=rank_df["Cor"].tolist()), legend=None),
        tooltip=["Usuario", "Equipe", "XP", "Horas"],
    ).properties(height=max(120, 46 * len(rank_df)))
    st.altair_chart(bar, width="stretch")

    st.write("")
    st.markdown("##### 🏅 Times")
    team_df = rank_df.groupby("Equipe").agg(XP=("XP", "sum"), Horas=("Horas", "sum"), Integrantes=("Usuario", "count")).reset_index().sort_values("XP", ascending=False)
    tcols = st.columns(min(3, max(1, len(team_df))))
    for i, (_, t) in enumerate(team_df.iterrows()):
        with tcols[i % len(tcols)]:
            kpi_card(st, "👥", t["Equipe"], f"{t['XP']} XP", f"{t['Horas']:.1f}h • {t['Integrantes']} pessoa(s)", ["bg-blue", "bg-violet", "bg-teal"][i % 3])

    st.write("")
    st.markdown("##### 📈 Corrida de horas (acumulado)")
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
        st.altair_chart(race_chart, width="stretch")
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
    st.markdown("#### 👥 Gerenciar pessoas e equipes")
    st.dataframe(usuarios, width="stretch", hide_index=True)

    st.markdown("### ➕ Adicionar nova pessoa")

    nc1, nc2, nc3 = st.columns(3)
    novo_nome = nc1.text_input("Nome", key="novo_nome_membro")
    nova_equipe = nc2.text_input("Equipe", value="Time Fluência", key="nova_equipe_membro")
    nova_cor = nc3.color_picker("Cor", value=dm.USER_PALETTE[len(usuarios) % len(dm.USER_PALETTE)], key="nova_cor_membro")

    data_inicio_plano = st.date_input(
        "📅 Data de início do plano desta pessoa",
        value=TODAY,
        help="O plano de 6 meses dessa pessoa vai começar nesta data (por padrão, hoje).",
        key="data_inicio_novo_membro",
    )
    data_fim_plano = dm.add_months(data_inicio_plano, 6)
    st.caption(f"O plano irá de **{data_inicio_plano.strftime('%d/%m/%Y')}** até **{data_fim_plano.strftime('%d/%m/%Y')}** (6 meses).")

    tipo_plano = st.radio(
        "Como montar o plano de estudos desta pessoa?",
        ["📋 Usar modelo padrão (English Live + Mairo Vergara)", "🎯 Personalizar (disponibilidade e materiais próprios)"],
        key="tipo_plano_membro",
    )

    disponibilidade_dict: dict = {}
    materiais_selecionados: list = []
    nova_meta = 14

    if tipo_plano.startswith("🎯"):
        st.markdown("##### 🗓️ Disponibilidade semanal")
        st.caption(
            "Adicione uma linha para cada horário livre que a pessoa tem (pode repetir o mesmo dia "
            "quantas vezes precisar — ex: Terça de manhã e Terça à noite). Use o botão **+** no final "
            "da tabela para adicionar mais linhas."
        )
        disponibilidade_editor = st.data_editor(
            pd.DataFrame(dm.DEFAULT_AVAILABILITY_ROWS),
            num_rows="dynamic",
            width="stretch",
            key="disponibilidade_editor_novo_membro",
            column_config={
                "Dia": st.column_config.SelectboxColumn("Dia da semana", options=dm.WEEKDAY_NAMES),
                "Horario": st.column_config.TextColumn("Horário (HH:MM)"),
                "Minutos": st.column_config.NumberColumn("Minutos disponíveis", min_value=0, step=5),
            },
        )
        disponibilidade_dict = dm.availability_rows_to_dict(disponibilidade_editor.to_dict("records"))
        minutos_semana = dm.weekly_minutes_from_availability(disponibilidade_dict)
        st.caption(f"⏱️ Total informado: **{minutos_semana} min/semana** ≈ **{minutos_semana/60:.1f}h/semana**")

        st.markdown("##### 📚 Materiais de estudo")
        materiais_catalogo = st.multiselect(
            "Selecione os materiais que essa pessoa vai usar (serão distribuídos em rodízio pelos horários acima):",
            options=list(dm.MATERIAL_CATALOG.keys()),
            default=["Anki (memorização)", "Mairo Vergara - Lição do dia", "English Live - Conversação em grupo"],
            key="materiais_catalogo_novo_membro",
        )
        materiais_selecionados = [{"nome": m, "habilidade": dm.MATERIAL_CATALOG[m]} for m in materiais_catalogo]

        with st.expander("➕ Adicionar material personalizado (não está na lista)"):
            cm1, cm2, cm3 = st.columns([2, 1, 1])
            custom_nome = cm1.text_input("Nome do material", key="custom_material_nome")
            custom_habilidade = cm2.selectbox("Habilidade que desenvolve", dm.SKILLS, key="custom_material_skill")
            if cm3.button("Adicionar", key="btn_add_custom_material"):
                if "materiais_customizados" not in st.session_state:
                    st.session_state.materiais_customizados = []
                if custom_nome.strip():
                    st.session_state.materiais_customizados.append({"nome": custom_nome, "habilidade": custom_habilidade})
                    st.success(f"'{custom_nome}' adicionado à lista personalizada!")
            if st.session_state.get("materiais_customizados"):
                st.caption("Materiais personalizados adicionados nesta sessão:")
                for m in st.session_state.materiais_customizados:
                    st.markdown(f"- **{m['nome']}** ({m['habilidade']})")
                materiais_selecionados = materiais_selecionados + st.session_state.materiais_customizados

        nova_meta_sugerida = round(minutos_semana / 60) if minutos_semana else 14
        nova_meta = st.number_input("Meta semanal (h)", min_value=1, max_value=80, value=int(nova_meta_sugerida), key="nova_meta_membro_personalizado")
    else:
        nova_meta = st.number_input("Meta semanal (h)", min_value=1, max_value=60, value=14, key="nova_meta_membro_padrao")

    if st.button("➕ Adicionar pessoa e gerar plano", type="primary"):
        if not novo_nome.strip():
            st.error("Informe um nome.")
        elif novo_nome in usuarios["Usuario"].tolist():
            st.error("Já existe uma pessoa com esse nome.")
        else:
            new_user_row = pd.DataFrame([{"Usuario": novo_nome, "Equipe": nova_equipe, "Cor": nova_cor, "MetaSemanal": nova_meta}])
            st.session_state.dfs["Usuarios"] = pd.concat([usuarios, new_user_row], ignore_index=True)
            max_id = int(atividades["ID"].max()) if len(atividades) else 0

            if tipo_plano.startswith("🎯"):
                novo_plano = dm.build_personalized_activities(
                    novo_nome, disponibilidade_dict, materiais_selecionados, max_id + 1,
                    start_date=data_inicio_plano, end_date=data_fim_plano,
                )
            else:
                novo_plano = dm.build_template_activities(
                    novo_nome, max_id + 1,
                    start_date=data_inicio_plano, end_date=data_fim_plano,
                )

            st.session_state.dfs["Atividades"] = pd.concat([atividades, novo_plano], ignore_index=True)
            st.session_state.pop("materiais_customizados", None)
            persist(f"Adicionar pessoa: {novo_nome} ({'personalizado' if tipo_plano.startswith('🎯') else 'padrão'})")
            st.success(f"{novo_nome} adicionado(a) com {len(novo_plano)} atividades geradas, começando em {data_inicio_plano.strftime('%d/%m/%Y')}!")
            st.rerun()

    if len(usuarios) > 1:
        with st.expander("🗑️ Remover pessoa"):
            remover = st.selectbox("Selecione", usuarios["Usuario"].tolist(), key="remover_sel")
            if st.button("Remover definitivamente", type="secondary"):
                st.session_state.dfs["Usuarios"] = usuarios[usuarios["Usuario"] != remover].reset_index(drop=True)
                st.session_state.dfs["Atividades"] = atividades[atividades["Usuario"] != remover].reset_index(drop=True)
                if st.session_state.current_user == remover:
                    st.session_state.current_user = st.session_state.dfs["Usuarios"].iloc[0]["Usuario"]
                persist(f"Remover pessoa: {remover}")
                st.rerun()

    st.divider()
    st.markdown("#### 💾 Backup e restauração")
    col_a, col_b = st.columns(2)
    with col_a:
        backup_bytes = dm.workbook_to_bytes(st.session_state.dfs)
        st.download_button("⬇️ Baixar backup (.xlsx)", data=backup_bytes, file_name="estudo_ingles_backup.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width="stretch")
    with col_b:
        if st.button("↺ Restaurar plano padrão de " + current_user + " (a partir de hoje)", width="stretch"):
            others = atividades[atividades["Usuario"] != current_user]
            max_id = int(others["ID"].max()) if len(others) else 0
            novo_plano = dm.build_template_activities(
                current_user, max_id + 1, start_date=TODAY, end_date=dm.add_months(TODAY, 6),
            )
            st.session_state.dfs["Atividades"] = pd.concat([others, novo_plano], ignore_index=True)
            persist(f"Restaurar plano padrão de {current_user}")
            st.success("Plano restaurado!")
            st.rerun()

    st.divider()
    st.markdown("#### 🔗 Conexão com o GitHub")
    if st.session_state.get("github_mode"):
        st.success("Conectado — todas as alterações são salvas automaticamente como commits no repositório configurado.")
    else:
        st.info(
            "Configure `GITHUB_TOKEN`, `GITHUB_REPO`, `GITHUB_BRANCH` e `GITHUB_FILE_PATH` em "
            "`.streamlit/secrets.toml` (local) ou em *Settings → Secrets* no Streamlit Community Cloud "
            "para habilitar o salvamento permanente e o acesso multi-dispositivo. Veja o README.md do projeto."
        )
