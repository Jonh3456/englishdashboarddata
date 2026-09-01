"""
Módulo de dados: estrutura do Excel, template do plano de 6 meses,
usuários padrão e helpers de leitura/escrita em memória (BytesIO).
"""
import io
from datetime import date, timedelta
import pandas as pd

START_DATE = date(2026, 8, 31)
END_DATE = date(2027, 2, 28)

SKILLS = ["Speaking", "Listening", "Writing", "Grammar", "Vocabulary"]
MODALITIES = ["English Live", "Mairo Vergara", "Estudo complementar"]

SKILL_COLORS = {
    "Speaking": "#2563eb",
    "Listening": "#8b5cf6",
    "Writing": "#14b8a6",
    "Grammar": "#f59e0b",
    "Vocabulary": "#ef4444",
}

USER_PALETTE = ["#2563eb", "#f97316", "#10b981", "#e11d48", "#a855f7", "#0ea5e9"]

ATIVIDADES_COLUMNS = [
    "ID", "Usuario", "Data", "Horario", "Tarefa", "Habilidade", "Modalidade",
    "MinutosPlanejados", "MinutosExecutados", "Concluido", "Anotacoes", "DataConclusao"
]

USUARIOS_COLUMNS = ["Usuario", "Equipe", "Cor", "MetaSemanal"]

# Template semanal: 0=Segunda ... 6=Domingo (isoweekday-1)
WEEKLY_TEMPLATE = {
    0: [  # Segunda - dia todo até 18h
        {"Tarefa": "Exercícios de gramática", "Habilidade": "Grammar", "Modalidade": "English Live", "MinutosPlanejados": 60, "Horario": "09:00"},
        {"Tarefa": "Lição do dia (Mairo Vergara)", "Habilidade": "Listening", "Modalidade": "Mairo Vergara", "MinutosPlanejados": 60, "Horario": "10:30"},
        {"Tarefa": "História em inglês (30 min)", "Habilidade": "Listening", "Modalidade": "Mairo Vergara", "MinutosPlanejados": 30, "Horario": "14:00"},
        {"Tarefa": "Conversação em grupo", "Habilidade": "Speaking", "Modalidade": "English Live", "MinutosPlanejados": 60, "Horario": "16:00"},
    ],
    1: [  # Terça - 40min manhã + 1h após 17:30
        {"Tarefa": "Anki (memorização)", "Habilidade": "Vocabulary", "Modalidade": "Mairo Vergara", "MinutosPlanejados": 40, "Horario": "06:40"},
        {"Tarefa": "Conversação em grupo", "Habilidade": "Speaking", "Modalidade": "English Live", "MinutosPlanejados": 60, "Horario": "17:30"},
    ],
    2: [  # Quarta - 40min manhã + 30min antes de dormir
        {"Tarefa": "História em inglês", "Habilidade": "Listening", "Modalidade": "Mairo Vergara", "MinutosPlanejados": 40, "Horario": "06:40"},
        {"Tarefa": "Diário em inglês", "Habilidade": "Writing", "Modalidade": "Estudo complementar", "MinutosPlanejados": 30, "Horario": "22:00"},
    ],
    3: [  # Quinta - 40min manhã + 1h após 18h
        {"Tarefa": "Anki e revisão gramatical", "Habilidade": "Grammar", "Modalidade": "English Live", "MinutosPlanejados": 40, "Horario": "06:40"},
        {"Tarefa": "Conversação com professor", "Habilidade": "Speaking", "Modalidade": "English Live", "MinutosPlanejados": 60, "Horario": "18:00"},
    ],
    4: [  # Sexta - dia todo até 18h
        {"Tarefa": "Lição do dia (Mairo Vergara)", "Habilidade": "Listening", "Modalidade": "Mairo Vergara", "MinutosPlanejados": 75, "Horario": "09:00"},
        {"Tarefa": "Audiobook Mairo Vergara", "Habilidade": "Listening", "Modalidade": "Mairo Vergara", "MinutosPlanejados": 60, "Horario": "11:00"},
        {"Tarefa": "Texto e correção", "Habilidade": "Writing", "Modalidade": "Estudo complementar", "MinutosPlanejados": 45, "Horario": "14:00"},
        {"Tarefa": "Gravação de voz (Speaking)", "Habilidade": "Speaking", "Modalidade": "Estudo complementar", "MinutosPlanejados": 30, "Horario": "16:00"},
    ],
    5: [  # Sábado - janela de 4h
        {"Tarefa": "Imersão: filme ou série em inglês", "Habilidade": "Listening", "Modalidade": "Estudo complementar", "MinutosPlanejados": 120, "Horario": "09:00"},
        {"Tarefa": "Lição e Anki", "Habilidade": "Vocabulary", "Modalidade": "Mairo Vergara", "MinutosPlanejados": 60, "Horario": "11:15"},
        {"Tarefa": "Speaking e resumo escrito", "Habilidade": "Speaking", "Modalidade": "Estudo complementar", "MinutosPlanejados": 60, "Horario": "14:00"},
    ],
    6: [  # Domingo
        {"Tarefa": "Revisão semanal e planejamento", "Habilidade": "Vocabulary", "Modalidade": "Estudo complementar", "MinutosPlanejados": 60, "Horario": "15:00"},
    ],
}


def build_template_activities(usuario: str, start_id: int) -> pd.DataFrame:
    """Gera o plano padrão de 6 meses (template semanal) para um usuário."""
    rows = []
    cursor = START_DATE
    next_id = start_id
    while cursor <= END_DATE:
        weekday = cursor.weekday()  # 0=Monday
        for item in WEEKLY_TEMPLATE.get(weekday, []):
            rows.append({
                "ID": next_id,
                "Usuario": usuario,
                "Data": cursor.isoformat(),
                "Horario": item["Horario"],
                "Tarefa": item["Tarefa"],
                "Habilidade": item["Habilidade"],
                "Modalidade": item["Modalidade"],
                "MinutosPlanejados": item["MinutosPlanejados"],
                "MinutosExecutados": 0,
                "Concluido": False,
                "Anotacoes": "",
                "DataConclusao": "",
            })
            next_id += 1
        cursor += timedelta(days=1)
    return pd.DataFrame(rows, columns=ATIVIDADES_COLUMNS)


def default_usuarios_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"Usuario": "Darlei", "Equipe": "Time Fluência", "Cor": USER_PALETTE[0], "MetaSemanal": 14},
        ],
        columns=USUARIOS_COLUMNS,
    )


def empty_atividades_df() -> pd.DataFrame:
    return pd.DataFrame(columns=ATIVIDADES_COLUMNS)


def workbook_to_bytes(dfs: dict) -> bytes:
    """Serializa um dicionário {nome_da_aba: DataFrame} em um .xlsx (bytes)."""
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, df in dfs.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    buffer.seek(0)
    return buffer.read()


def bytes_to_workbook(content: bytes) -> dict:
    """Lê um .xlsx (bytes) e devolve {nome_da_aba: DataFrame}."""
    buffer = io.BytesIO(content)
    xls = pd.ExcelFile(buffer, engine="openpyxl")
    result = {}
    for sheet_name in xls.sheet_names:
        result[sheet_name] = xls.parse(sheet_name)
    return result


def normalize_atividades(df: pd.DataFrame) -> pd.DataFrame:
    """Garante tipos e colunas corretas após leitura do Excel."""
    if df.empty:
        return empty_atividades_df()
    for col in ATIVIDADES_COLUMNS:
        if col not in df.columns:
            df[col] = "" if col not in ("ID", "MinutosPlanejados", "MinutosExecutados", "Concluido") else 0
    df["ID"] = pd.to_numeric(df["ID"], errors="coerce").fillna(0).astype(int)
    df["MinutosPlanejados"] = pd.to_numeric(df["MinutosPlanejados"], errors="coerce").fillna(0).astype(int)
    df["MinutosExecutados"] = pd.to_numeric(df["MinutosExecutados"], errors="coerce").fillna(0).astype(int)
    df["Concluido"] = df["Concluido"].apply(lambda v: str(v).strip().lower() in ("true", "1", "sim", "yes"))
    df["Data"] = df["Data"].astype(str)
    df["Horario"] = df["Horario"].astype(str)
    df["Anotacoes"] = df["Anotacoes"].fillna("").astype(str)
    df["DataConclusao"] = df["DataConclusao"].fillna("").astype(str)
    return df[ATIVIDADES_COLUMNS]


def normalize_usuarios(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return default_usuarios_df()
    for col in USUARIOS_COLUMNS:
        if col not in df.columns:
            df[col] = 14 if col == "MetaSemanal" else ""
    df["MetaSemanal"] = pd.to_numeric(df["MetaSemanal"], errors="coerce").fillna(14).astype(int)
    return df[USUARIOS_COLUMNS]
