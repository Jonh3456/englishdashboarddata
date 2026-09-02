"""
Modelo de dados do English Journey Dashboard.

Contém: constantes do plano (datas, habilidades, modalidades, cores),
o esquema de colunas das duas planilhas (Atividades / Usuarios),
a geração do plano padrão de 6 meses, a geração de um plano
PERSONALIZADO (baseado na disponibilidade e materiais de cada pessoa)
e as funções de (de)serialização para Excel (usadas pelo github_sync).

IMPORTANTE: cada pessoa tem seu próprio período de 6 meses, que começa
no dia em que ela é cadastrada (não em uma data fixa) — ver add_months()
e as funções build_template_activities / build_personalized_activities.
"""
from __future__ import annotations

import calendar
import io
from datetime import date, timedelta

import pandas as pd

# ============================================================
# CONSTANTES GERAIS DO PLANO (usadas apenas como padrão do usuário inicial
# "Você", criado automaticamente na primeira execução do app)
# ============================================================
START_DATE = date(2026, 8, 31)
END_DATE = date(2027, 2, 28)

SKILLS = ["Speaking", "Listening", "Writing", "Grammar", "Vocabulary"]
MODALITIES = ["English Live", "Mairo Vergara", "Estudo complementar", "Personalizado"]

SKILL_COLORS = {
    "Speaking": "#2563eb",
    "Listening": "#8b5cf6",
    "Writing": "#14b8a6",
    "Grammar": "#f59e0b",
    "Vocabulary": "#ef4444",
}

USER_PALETTE = ["#2563eb", "#f97316", "#10b981", "#a855f7", "#ec4899", "#0ea5e9"]

WEEKDAY_NAMES = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

# Catálogo de materiais sugeridos para o plano PERSONALIZADO.
# Cada material já vem associado à habilidade que ele desenvolve principalmente,
# para que o app consiga distribuir e classificar automaticamente as sessões geradas.
MATERIAL_CATALOG: dict[str, str] = {
    "Anki (memorização)": "Vocabulary",
    "Mairo Vergara - Lição do dia": "Grammar",
    "Mairo Vergara - Áudio/História": "Listening",
    "Mairo Vergara - Audiobook": "Listening",
    "English Live - Exercício de gramática": "Grammar",
    "English Live - Conversação em grupo": "Speaking",
    "English Live - Aula com professor": "Speaking",
    "Filme/Série legendado": "Listening",
    "Podcast em inglês": "Listening",
    "Livro/Leitura": "Vocabulary",
    "Diário/Redação": "Writing",
    "Gravação de voz (Speaking)": "Speaking",
}

# ============================================================
# ESQUEMA DAS PLANILHAS
# ============================================================
ATIVIDADES_COLUMNS = [
    "ID", "Usuario", "Data", "Horario", "Tarefa", "Habilidade", "Modalidade",
    "MinutosPlanejados", "MinutosExecutados", "Concluido", "Anotacoes", "DataConclusao",
]
USUARIOS_COLUMNS = ["Usuario", "Equipe", "Cor", "MetaSemanal"]

# ============================================================
# TEMPLATE SEMANAL PADRÃO (0 = Segunda ... 6 = Domingo, igual a date.weekday())
# ============================================================
WEEKLY_TEMPLATE = {
    0: [  # Segunda - dia todo até 18h
        dict(tarefa="Exercícios de gramática", habilidade="Grammar", modalidade="English Live", minutos=60, horario="09:00"),
        dict(tarefa="Lição do dia (Mairo Vergara)", habilidade="Listening", modalidade="Mairo Vergara", minutos=60, horario="10:30"),
        dict(tarefa="História em inglês (30 min)", habilidade="Listening", modalidade="Mairo Vergara", minutos=30, horario="14:00"),
        dict(tarefa="Conversação em grupo", habilidade="Speaking", modalidade="English Live", minutos=60, horario="16:00"),
    ],
    1: [  # Terça - 40min manhã + 1h após 17:30
        dict(tarefa="Anki (memorização)", habilidade="Vocabulary", modalidade="Mairo Vergara", minutos=40, horario="06:40"),
        dict(tarefa="Conversação em grupo", habilidade="Speaking", modalidade="English Live", minutos=60, horario="17:30"),
    ],
    2: [  # Quarta - 40min manhã + 30min antes de dormir
        dict(tarefa="História em inglês", habilidade="Listening", modalidade="Mairo Vergara", minutos=40, horario="06:40"),
        dict(tarefa="Diário em inglês", habilidade="Writing", modalidade="Estudo complementar", minutos=30, horario="22:00"),
    ],
    3: [  # Quinta - 40min manhã + 1h após 18h
        dict(tarefa="Anki e revisão gramatical", habilidade="Grammar", modalidade="English Live", minutos=40, horario="06:40"),
        dict(tarefa="Conversação com professor", habilidade="Speaking", modalidade="English Live", minutos=60, horario="18:00"),
    ],
    4: [  # Sexta - dia todo até 18h
        dict(tarefa="Lição do dia (Mairo Vergara)", habilidade="Listening", modalidade="Mairo Vergara", minutos=75, horario="09:00"),
        dict(tarefa="Audiobook Mairo Vergara", habilidade="Listening", modalidade="Mairo Vergara", minutos=60, horario="11:00"),
        dict(tarefa="Texto e correção", habilidade="Writing", modalidade="Estudo complementar", minutos=45, horario="14:00"),
        dict(tarefa="Gravação de voz (Speaking)", habilidade="Speaking", modalidade="Estudo complementar", minutos=30, horario="16:00"),
    ],
    5: [  # Sábado - janela de 4h
        dict(tarefa="Imersão: filme ou série em inglês", habilidade="Listening", modalidade="Estudo complementar", minutos=120, horario="09:00"),
        dict(tarefa="Lição e Anki", habilidade="Vocabulary", modalidade="Mairo Vergara", minutos=60, horario="11:15"),
        dict(tarefa="Speaking e resumo escrito", habilidade="Speaking", modalidade="Estudo complementar", minutos=60, horario="14:00"),
    ],
    6: [  # Domingo
        dict(tarefa="Revisão semanal e planejamento", habilidade="Vocabulary", modalidade="Estudo complementar", minutos=60, horario="15:00"),
    ],
}

# Disponibilidade padrão sugerida quando a pessoa escolhe "Personalizar" mas
# ainda não editou a tabela — serve como ponto de partida amigável.
DEFAULT_AVAILABILITY_ROWS = [
    {"Dia": "Segunda", "Horario": "09:00", "Minutos": 60},
    {"Dia": "Terça", "Horario": "06:40", "Minutos": 40},
    {"Dia": "Terça", "Horario": "17:30", "Minutos": 60},
    {"Dia": "Quarta", "Horario": "06:40", "Minutos": 40},
    {"Dia": "Quarta", "Horario": "22:00", "Minutos": 30},
    {"Dia": "Quinta", "Horario": "06:40", "Minutos": 40},
    {"Dia": "Quinta", "Horario": "18:00", "Minutos": 60},
    {"Dia": "Sexta", "Horario": "09:00", "Minutos": 90},
    {"Dia": "Sábado", "Horario": "10:00", "Minutos": 120},
    {"Dia": "Domingo", "Horario": "15:00", "Minutos": 60},
]


# ============================================================
# HELPER DE DATA — soma "meses" a uma data sem depender de dateutil
# ============================================================
def add_months(d: date, months: int) -> date:
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


# ============================================================
# DATAFRAMES VAZIOS / PADRÃO
# ============================================================
def empty_atividades_df() -> pd.DataFrame:
    return pd.DataFrame(columns=ATIVIDADES_COLUMNS)


def default_usuarios_df() -> pd.DataFrame:
    return pd.DataFrame(
        [{"Usuario": "Você", "Equipe": "Equipe Principal", "Cor": USER_PALETTE[0], "MetaSemanal": 14}],
        columns=USUARIOS_COLUMNS,
    )


# ============================================================
# GERAÇÃO DO PLANO PADRÃO (MODELO CLÁSSICO)
# ============================================================
def build_template_activities(
    usuario: str,
    start_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> pd.DataFrame:
    """Gera o plano de 6 meses seguindo o template semanal padrão.

    Se start_date/end_date não forem informados, usa a janela padrão do
    projeto (START_DATE/END_DATE). Ao adicionar uma NOVA pessoa pelo app,
    o app.py deve passar start_date=hoje e end_date=hoje+6 meses, para que
    o plano dela comece no dia do cadastro.
    """
    start_date = start_date or START_DATE
    end_date = end_date or END_DATE

    linhas = []
    cursor = start_date
    next_id = start_id
    while cursor <= end_date:
        for item in WEEKLY_TEMPLATE.get(cursor.weekday(), []):
            linhas.append({
                "ID": next_id, "Usuario": usuario, "Data": cursor.isoformat(),
                "Horario": item["horario"], "Tarefa": item["tarefa"],
                "Habilidade": item["habilidade"], "Modalidade": item["modalidade"],
                "MinutosPlanejados": item["minutos"], "MinutosExecutados": 0,
                "Concluido": False, "Anotacoes": "", "DataConclusao": "",
            })
            next_id += 1
        cursor += timedelta(days=1)
    return pd.DataFrame(linhas, columns=ATIVIDADES_COLUMNS)


# ============================================================
# GERAÇÃO DO PLANO PERSONALIZADO
# ============================================================
def build_personalized_activities(
    usuario: str,
    disponibilidade: dict[int, list[dict]],
    materiais: list[dict],
    start_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
) -> pd.DataFrame:
    """
    disponibilidade: {weekday_idx (0=Segunda..6=Domingo): [{"horario": "HH:MM", "minutos": int}, ...]}
    materiais: [{"nome": str, "habilidade": str}, ...] — usados em rodízio (round-robin)
               ao longo do período, na ordem em que a pessoa escolheu.
    start_date/end_date: janela do plano desta pessoa. Se omitidos, usa a
        janela padrão do projeto (START_DATE/END_DATE).
    """
    start_date = start_date or START_DATE
    end_date = end_date or END_DATE

    if not materiais:
        materiais = [{"nome": "Estudo livre", "habilidade": s} for s in SKILLS]

    linhas = []
    cursor = start_date
    next_id = start_id
    mat_idx = 0
    n = len(materiais)

    while cursor <= end_date:
        blocos = disponibilidade.get(cursor.weekday(), [])
        # ordena os blocos do dia por horário para manter a agenda em ordem cronológica
        blocos_ordenados = sorted(blocos, key=lambda b: str(b.get("horario", "")))
        for bloco in blocos_ordenados:
            minutos = int(bloco.get("minutos", 0) or 0)
            if minutos <= 0:
                continue
            material = materiais[mat_idx % n]
            mat_idx += 1
            linhas.append({
                "ID": next_id, "Usuario": usuario, "Data": cursor.isoformat(),
                "Horario": str(bloco.get("horario", "18:00")), "Tarefa": material["nome"],
                "Habilidade": material["habilidade"], "Modalidade": "Personalizado",
                "MinutosPlanejados": minutos, "MinutosExecutados": 0,
                "Concluido": False, "Anotacoes": "", "DataConclusao": "",
            })
            next_id += 1
        cursor += timedelta(days=1)
    return pd.DataFrame(linhas, columns=ATIVIDADES_COLUMNS)


def weekly_minutes_from_availability(disponibilidade: dict[int, list[dict]]) -> int:
    """Soma os minutos de uma semana típica de disponibilidade (para sugerir a meta semanal)."""
    total = 0
    for blocos in disponibilidade.values():
        for b in blocos:
            total += int(b.get("minutos", 0) or 0)
    return total


def availability_rows_to_dict(rows: list[dict]) -> dict[int, list[dict]]:
    """Converte linhas vindas de um st.data_editor (colunas Dia/Horario/Minutos) para o dict por weekday."""
    nome_para_idx = {nome: i for i, nome in enumerate(WEEKDAY_NAMES)}
    disponibilidade: dict[int, list[dict]] = {i: [] for i in range(7)}
    for row in rows:
        dia = row.get("Dia")
        idx = nome_para_idx.get(dia)
        minutos = row.get("Minutos", 0) or 0
        horario = row.get("Horario", "18:00") or "18:00"
        if idx is None or int(minutos) <= 0:
            continue
        disponibilidade[idx].append({"horario": str(horario), "minutos": int(minutos)})
    return disponibilidade


# ============================================================
# NORMALIZAÇÃO (garante colunas/tipos corretos ao carregar do Excel)
# ============================================================
def normalize_atividades(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in ATIVIDADES_COLUMNS:
        if col not in df.columns:
            if col in ("Anotacoes", "DataConclusao"):
                df[col] = ""
            elif col == "Concluido":
                df[col] = False
            else:
                df[col] = 0
    df["Concluido"] = df["Concluido"].fillna(False).astype(bool)
    df["Data"] = df["Data"].astype(str)
    df["Horario"] = df["Horario"].astype(str)
    df["Anotacoes"] = df["Anotacoes"].fillna("").astype(str)
    df["DataConclusao"] = df["DataConclusao"].fillna("").astype(str)
    df["MinutosPlanejados"] = pd.to_numeric(df["MinutosPlanejados"], errors="coerce").fillna(0).astype(int)
    df["MinutosExecutados"] = pd.to_numeric(df["MinutosExecutados"], errors="coerce").fillna(0).astype(int)
    df["ID"] = pd.to_numeric(df["ID"], errors="coerce").fillna(0).astype(int)
    return df[ATIVIDADES_COLUMNS]


def normalize_usuarios(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for col in USUARIOS_COLUMNS:
        if col not in df.columns:
            df[col] = 14 if col == "MetaSemanal" else ""
    df["MetaSemanal"] = pd.to_numeric(df["MetaSemanal"], errors="coerce").fillna(14).astype(int)
    return df[USUARIOS_COLUMNS]


# ============================================================
# (DE)SERIALIZAÇÃO EXCEL — usado pelo github_sync para persistir/carregar
# ============================================================
def workbook_to_bytes(dfs: dict) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        dfs["Atividades"].to_excel(writer, sheet_name="Atividades", index=False)
        dfs["Usuarios"].to_excel(writer, sheet_name="Usuarios", index=False)
    buffer.seek(0)
    return buffer.read()


def bytes_to_workbook(content: bytes) -> dict:
    xls = pd.ExcelFile(io.BytesIO(content))
    result = {}
    if "Atividades" in xls.sheet_names:
        result["Atividades"] = pd.read_excel(xls, "Atividades")
    if "Usuarios" in xls.sheet_names:
        result["Usuarios"] = pd.read_excel(xls, "Usuarios")
    return result
