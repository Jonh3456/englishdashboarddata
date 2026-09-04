"""
Módulo de dados: estrutura do Excel, template do plano de 6 meses,
catálogo de materiais para o plano personalizado, distribuição inteligente
(empacotamento) dos materiais nos horários livres, usuários (com suporte a
administrador) e helpers de leitura/escrita em memória (BytesIO).

IMPORTANTE: cada pessoa tem seu próprio período de 6 meses, que começa no
dia em que ela cria a conta (não em uma data fixa do projeto).
"""
from __future__ import annotations

import calendar
import hashlib
import io
import json
from datetime import date, timedelta

import pandas as pd

# Janela padrão usada apenas como fallback (ex: usuário-semente antes de
# qualquer dado existir no GitHub). Cada pessoa real tem sua própria janela
# de 6 meses, começando no dia em que ela cria a conta.
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

USER_PALETTE = ["#2563eb", "#f97316", "#10b981", "#e11d48", "#a855f7", "#0ea5e9"]

WEEKDAY_NAMES = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

ATIVIDADES_COLUMNS = [
    "ID", "Usuario", "Data", "Horario", "Tarefa", "Habilidade", "Modalidade",
    "MinutosPlanejados", "MinutosExecutados", "Concluido", "Anotacoes", "DataConclusao",
]

# "IsAdmin" habilita o Modo Admin (gerenciar/remover pessoas) para quem tiver True.
# "TipoPlano" ("padrao" ou "personalizado"), "DisponibilidadeJSON", "MateriaisJSON"
# e "DuracoesPadraoJSON" guardam a configuração de cronograma da pessoa (a mesma
# que ela escolheu no cadastro), para permitir reabrir e editar depois em
# "Editar meu perfil de estudo", sem precisar redigitar tudo do zero.
USUARIOS_COLUMNS = [
    "Usuario", "Equipe", "Cor", "MetaSemanal", "SenhaHash", "IsAdmin",
    "TipoPlano", "DisponibilidadeJSON", "MateriaisJSON", "DuracoesPadraoJSON",
]

# ============================================================
# TEMPLATE SEMANAL PADRÃO (modelo "📋 Usar modelo padrão")
# 0=Segunda ... 6=Domingo (igual a date.weekday())
# ============================================================
WEEKLY_TEMPLATE = {
    0: [
        {"Tarefa": "Exercícios de gramática", "Habilidade": "Grammar", "Modalidade": "English Live", "MinutosPlanejados": 60, "Horario": "09:00"},
        {"Tarefa": "Lição do dia (Mairo Vergara)", "Habilidade": "Listening", "Modalidade": "Mairo Vergara", "MinutosPlanejados": 60, "Horario": "10:30"},
        {"Tarefa": "História em inglês (30 min)", "Habilidade": "Listening", "Modalidade": "Mairo Vergara", "MinutosPlanejados": 30, "Horario": "14:00"},
        {"Tarefa": "Conversação em grupo", "Habilidade": "Speaking", "Modalidade": "English Live", "MinutosPlanejados": 60, "Horario": "16:00"},
    ],
    1: [
        {"Tarefa": "Anki (memorização)", "Habilidade": "Vocabulary", "Modalidade": "Mairo Vergara", "MinutosPlanejados": 40, "Horario": "06:40"},
        {"Tarefa": "Conversação em grupo", "Habilidade": "Speaking", "Modalidade": "English Live", "MinutosPlanejados": 60, "Horario": "17:30"},
    ],
    2: [
        {"Tarefa": "História em inglês", "Habilidade": "Listening", "Modalidade": "Mairo Vergara", "MinutosPlanejados": 40, "Horario": "06:40"},
        {"Tarefa": "Diário em inglês", "Habilidade": "Writing", "Modalidade": "Estudo complementar", "MinutosPlanejados": 30, "Horario": "22:00"},
    ],
    3: [
        {"Tarefa": "Anki e revisão gramatical", "Habilidade": "Grammar", "Modalidade": "English Live", "MinutosPlanejados": 40, "Horario": "06:40"},
        {"Tarefa": "Conversação com professor", "Habilidade": "Speaking", "Modalidade": "English Live", "MinutosPlanejados": 60, "Horario": "18:00"},
    ],
    4: [
        {"Tarefa": "Lição do dia (Mairo Vergara)", "Habilidade": "Listening", "Modalidade": "Mairo Vergara", "MinutosPlanejados": 75, "Horario": "09:00"},
        {"Tarefa": "Audiobook Mairo Vergara", "Habilidade": "Listening", "Modalidade": "Mairo Vergara", "MinutosPlanejados": 60, "Horario": "11:00"},
        {"Tarefa": "Texto e correção", "Habilidade": "Writing", "Modalidade": "Estudo complementar", "MinutosPlanejados": 45, "Horario": "14:00"},
        {"Tarefa": "Gravação de voz (Speaking)", "Habilidade": "Speaking", "Modalidade": "Estudo complementar", "MinutosPlanejados": 30, "Horario": "16:00"},
    ],
    5: [
        {"Tarefa": "Imersão: filme ou série em inglês", "Habilidade": "Listening", "Modalidade": "Estudo complementar", "MinutosPlanejados": 120, "Horario": "09:00"},
        {"Tarefa": "Lição e Anki", "Habilidade": "Vocabulary", "Modalidade": "Mairo Vergara", "MinutosPlanejados": 60, "Horario": "11:15"},
        {"Tarefa": "Speaking e resumo escrito", "Habilidade": "Speaking", "Modalidade": "Estudo complementar", "MinutosPlanejados": 60, "Horario": "14:00"},
    ],
    6: [
        {"Tarefa": "Revisão semanal e planejamento", "Habilidade": "Vocabulary", "Modalidade": "Estudo complementar", "MinutosPlanejados": 60, "Horario": "15:00"},
    ],
}

# ============================================================
# CATÁLOGO DE MATERIAIS (modelo "🎯 Personalizar")
# ============================================================
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

# Duração PADRÃO sugerida (minutos) para cada material do catálogo acima.
# Serve como valor inicial nos campos de duração (+/-) — a pessoa pode
# ajustar livremente antes de gerar o calendário.
DEFAULT_MATERIAL_DURATIONS: dict[str, int] = {
    "Anki (memorização)": 20,
    "Mairo Vergara - Lição do dia": 45,
    "Mairo Vergara - Áudio/História": 30,
    "Mairo Vergara - Audiobook": 45,
    "English Live - Exercício de gramática": 45,
    "English Live - Conversação em grupo": 60,
    "English Live - Aula com professor": 60,
    "Filme/Série legendado": 90,
    "Podcast em inglês": 30,
    "Livro/Leitura": 30,
    "Diário/Redação": 30,
    "Gravação de voz (Speaking)": 20,
}
DEFAULT_CUSTOM_MATERIAL_DURATION = 30  # fallback para material fora do catálogo


def get_default_duration(nome_material: str) -> int:
    """Duração padrão (minutos) de um material. Cai para um valor genérico
    se o material não estiver no catálogo (ex: material customizado sem
    duração própria informada)."""
    return DEFAULT_MATERIAL_DURATIONS.get(nome_material, DEFAULT_CUSTOM_MATERIAL_DURATION)


def list_template_task_names() -> list[str]:
    """Lista (sem repetição, na ordem de aparição) as tarefas do template
    semanal clássico — usada para montar os campos de duração (+/-) do
    modelo padrão."""
    vistos: list[str] = []
    for _, itens in sorted(WEEKLY_TEMPLATE.items()):
        for item in itens:
            if item["Tarefa"] not in vistos:
                vistos.append(item["Tarefa"])
    return vistos


def template_task_default_duration(nome_tarefa: str) -> int:
    """Duração padrão (minutos) de uma tarefa do template clássico."""
    for _, itens in WEEKLY_TEMPLATE.items():
        for item in itens:
            if item["Tarefa"] == nome_tarefa:
                return item["MinutosPlanejados"]
    return DEFAULT_CUSTOM_MATERIAL_DURATION


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
    {"Dia": "Sábado", "Horario": "11:00", "Minutos": 120},
    {"Dia": "Domingo", "Horario": "15:00", "Minutos": 60},
]


def add_months(d: date, months: int) -> date:
    """Soma meses a uma data, respeitando o número de dias de cada mês
    (ex: 31/jan + 1 mês = 28/fev, não 31/fev)."""
    month_index = d.month - 1 + months
    year = d.year + month_index // 12
    month = month_index % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def hash_password(raw: str) -> str:
    """Hash SHA-256 do PIN/senha (nunca guardamos texto puro)."""
    return hashlib.sha256((raw or "").encode("utf-8")).hexdigest()


# ============================================================
# GERAÇÃO DO PLANO — MODELO PADRÃO
# ============================================================
def build_template_activities(
    usuario: str,
    start_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    custom_durations: dict[str, int] | None = None,
) -> pd.DataFrame:
    """Gera o plano seguindo o template semanal padrão.

    custom_durations: dict opcional {nome_da_tarefa: minutos}. Substitui a
    duração padrão daquela tarefa em TODAS as ocorrências dela no
    cronograma. Tarefas não presentes no dict mantêm a duração original.
    """
    start_date = start_date or START_DATE
    end_date = end_date or END_DATE
    custom_durations = custom_durations or {}

    rows = []
    cursor = start_date
    next_id = start_id
    while cursor <= end_date:
        for item in WEEKLY_TEMPLATE.get(cursor.weekday(), []):
            duracao = custom_durations.get(item["Tarefa"], item["MinutosPlanejados"])
            rows.append({
                "ID": next_id, "Usuario": usuario, "Data": cursor.isoformat(),
                "Horario": item["Horario"], "Tarefa": item["Tarefa"],
                "Habilidade": item["Habilidade"], "Modalidade": item["Modalidade"],
                "MinutosPlanejados": int(duracao), "MinutosExecutados": 0,
                "Concluido": False, "Anotacoes": "", "DataConclusao": "",
            })
            next_id += 1
        cursor += timedelta(days=1)
    return pd.DataFrame(rows, columns=ATIVIDADES_COLUMNS)


# ============================================================
# GERAÇÃO DO PLANO — PERSONALIZADO (com distribuição inteligente)
# ============================================================
def _minutes_to_hhmm(total_minutes: int) -> str:
    total_minutes = total_minutes % (24 * 60)
    return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"


def _hhmm_to_minutes(hhmm: str) -> int:
    try:
        h, m = str(hhmm).split(":")
        return int(h) * 60 + int(m)
    except Exception:  # noqa: BLE001
        return 18 * 60


def build_personalized_activities(
    usuario: str,
    disponibilidade: dict[int, list[dict]],
    materiais: list[dict],
    start_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    material_durations: dict[str, int] | None = None,
) -> pd.DataFrame:
    """
    disponibilidade: {weekday_idx (0=Segunda..6=Domingo): [{"horario": "HH:MM", "minutos": int}, ...]}
    materiais: [{"nome": str, "habilidade": str}, ...] — usados em rodízio contínuo
        (a rotação continua de um bloco/dia para o outro, ao longo de todo o plano).
    material_durations: dict opcional {nome_do_material: minutos}. Define a duração
        de CADA tarefa gerada com aquele material. Se um material não estiver no
        dict, usa get_default_duration(nome) como duração-base.

    DISTRIBUIÇÃO INTELIGENTE (empacotamento):
    Em vez de "1 material = 1 bloco de disponibilidade" (que desperdiçava tempo
    quando o bloco era maior que a tarefa, ou estourava o horário quando o bloco
    era menor), cada bloco de disponibilidade agora é preenchido com quantas
    tarefas couberem nele, respeitando a duração de cada material:
      - Começa no horário do bloco e vai encaixando materiais em rodízio.
      - Se o próximo material da fila não couber no tempo que resta do bloco,
        tenta os próximos da fila (até dar uma volta completa) — assim um
        material curto pode "preencher" o restante antes de pular para o
        próximo bloco.
      - Se nenhum material da lista couber no tempo restante, o restante do
        bloco fica ocioso (não força um material a ficar menor que o
        planejado) e o algoritmo passa para o próximo bloco/dia.
    """
    start_date = start_date or START_DATE
    end_date = end_date or END_DATE
    material_durations = material_durations or {}

    if not materiais:
        materiais = [{"nome": "Estudo livre", "habilidade": s} for s in SKILLS]

    n = len(materiais)
    durations = [
        max(5, int(material_durations.get(m["nome"], get_default_duration(m["nome"])) or get_default_duration(m["nome"])))
        for m in materiais
    ]

    rows = []
    cursor = start_date
    next_id = start_id
    mat_idx = 0  # ponteiro de rodízio contínuo (persiste entre blocos/dias)

    while cursor <= end_date:
        blocos = sorted(
            disponibilidade.get(cursor.weekday(), []),
            key=lambda b: str(b.get("horario", "")),
        )
        for bloco in blocos:
            block_minutes = int(bloco.get("minutos", 0) or 0)
            if block_minutes <= 0:
                continue
            current_minute = _hhmm_to_minutes(bloco.get("horario", "18:00"))
            remaining = block_minutes

            while remaining > 0:
                placed = False
                for step in range(n):
                    idx = (mat_idx + step) % n
                    duracao = durations[idx]
                    if duracao <= remaining:
                        material = materiais[idx]
                        rows.append({
                            "ID": next_id, "Usuario": usuario, "Data": cursor.isoformat(),
                            "Horario": _minutes_to_hhmm(current_minute), "Tarefa": material["nome"],
                            "Habilidade": material["habilidade"], "Modalidade": "Personalizado",
                            "MinutosPlanejados": int(duracao), "MinutosExecutados": 0,
                            "Concluido": False, "Anotacoes": "", "DataConclusao": "",
                        })
                        next_id += 1
                        current_minute += duracao
                        remaining -= duracao
                        mat_idx = (idx + 1) % n
                        placed = True
                        break
                if not placed:
                    # Nenhum material cabe no tempo restante deste bloco — para
                    # de preencher este bloco e segue para o próximo.
                    break
        cursor += timedelta(days=1)
    return pd.DataFrame(rows, columns=ATIVIDADES_COLUMNS)


def weekly_minutes_from_availability(disponibilidade: dict[int, list[dict]]) -> int:
    total = 0
    for blocos in disponibilidade.values():
        for b in blocos:
            total += int(b.get("minutos", 0) or 0)
    return total


def availability_rows_to_dict(rows: list[dict]) -> dict[int, list[dict]]:
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
# USUÁRIOS / ADMIN
# ============================================================
def default_usuarios_df() -> pd.DataFrame:
    """Usuário-semente, criado apenas se ainda não existir nenhum dado no
    GitHub. É sempre administrador, para garantir que sempre exista alguém
    com acesso ao Modo Admin."""
    return pd.DataFrame(
        [{"Usuario": "Admin", "Equipe": "Time Fluência", "Cor": USER_PALETTE[0],
          "MetaSemanal": 14, "SenhaHash": "", "IsAdmin": True,
          "TipoPlano": "padrao", "DisponibilidadeJSON": "[]", "MateriaisJSON": "[]",
          "DuracoesPadraoJSON": "{}"}],
        columns=USUARIOS_COLUMNS,
    )


def ensure_admin(df: pd.DataFrame) -> pd.DataFrame:
    """Garante que exista pelo menos um administrador na tabela de
    usuários. Se ninguém for admin (ex: após uma migração de esquema
    antiga), promove a primeira pessoa da lista."""
    if df.empty:
        return df
    if "IsAdmin" not in df.columns:
        df = df.copy()
        df["IsAdmin"] = False
    if not bool(df["IsAdmin"].any()):
        df = df.copy()
        df.iloc[0, df.columns.get_loc("IsAdmin")] = True
    return df


# ============================================================
# PERSISTÊNCIA DO PERFIL DE ESTUDO (disponibilidade + materiais + duração)
# Guardado como JSON dentro da própria aba Usuarios, para permitir reabrir
# e editar o cronograma depois em "Editar meu perfil de estudo".
# ============================================================
def availability_rows_to_json(rows: list[dict]) -> str:
    """Serializa as linhas de disponibilidade (Dia/Horario/Minutos) para JSON."""
    limpo = [
        {"Dia": r.get("Dia", ""), "Horario": str(r.get("Horario", "18:00")), "Minutos": int(r.get("Minutos", 0) or 0)}
        for r in rows if r.get("Dia") and int(r.get("Minutos", 0) or 0) > 0
    ]
    return json.dumps(limpo, ensure_ascii=False)


def availability_rows_from_json(json_str: str) -> list[dict]:
    """Desserializa as linhas de disponibilidade salvas (para pré-preencher o editor)."""
    try:
        rows = json.loads(json_str) if json_str else []
        return rows if isinstance(rows, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def materials_to_json(materiais: list[dict], durations: dict[str, int] | None = None) -> str:
    """Serializa a lista de materiais (com a duração de cada um) para JSON."""
    durations = durations or {}
    limpo = [
        {
            "nome": m["nome"], "habilidade": m["habilidade"],
            "minutos": int(durations.get(m["nome"], m.get("minutos", get_default_duration(m["nome"])))),
        }
        for m in materiais
    ]
    return json.dumps(limpo, ensure_ascii=False)


def materials_from_json(json_str: str) -> list[dict]:
    """Desserializa os materiais salvos (para pré-preencher o editor de perfil)."""
    try:
        materiais = json.loads(json_str) if json_str else []
        return materiais if isinstance(materiais, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def durations_dict_to_json(durations: dict[str, int]) -> str:
    """Serializa o dict {tarefa: minutos} do modelo padrão para JSON."""
    return json.dumps(durations or {}, ensure_ascii=False)


def durations_dict_from_json(json_str: str) -> dict[str, int]:
    """Desserializa o dict de durações do modelo padrão salvo."""
    try:
        d = json.loads(json_str) if json_str else {}
        return {k: int(v) for k, v in d.items()} if isinstance(d, dict) else {}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


# ============================================================
# RECORRÊNCIA — geração de datas repetidas para uma nova atividade
# ============================================================
FREQUENCIAS_RECORRENCIA = ["Não recorrente", "Diariamente", "Semanalmente", "Mensalmente"]


def generate_recurring_dates(start_date: date, end_date: date, frequencia: str) -> list[date]:
    """Gera a lista de datas de ocorrência de uma atividade recorrente, do
    início até o limite (inclusive), conforme a frequência escolhida."""
    if end_date < start_date:
        return [start_date]
    datas = []
    cursor = start_date
    if frequencia == "Diariamente":
        while cursor <= end_date:
            datas.append(cursor)
            cursor += timedelta(days=1)
    elif frequencia == "Semanalmente":
        while cursor <= end_date:
            datas.append(cursor)
            cursor += timedelta(days=7)
    elif frequencia == "Mensalmente":
        while cursor <= end_date:
            datas.append(cursor)
            cursor = add_months(cursor, 1)
    else:  # "Não recorrente" (ou qualquer valor desconhecido) — só a data inicial
        datas.append(start_date)
    return datas


# ============================================================
# NÍVEIS — nomes temáticos para cada nível de XP (usado na tela Conquistas)
# ============================================================
LEVEL_XP_STEP = 500  # mesmo valor usado em "xp // 500 + 1" no cálculo de nível

LEVEL_NAMES = [
    "Explorador do Inglês",
    "Aprendiz Dedicado",
    "Comunicador Iniciante",
    "Falante Confiante",
    "Fluência em Construção",
    "Quase Fluente",
    "Fluente",
    "Mestre da Conversação",
    "Poliglota em Ascensão",
    "Lenda do Inglês",
]


def level_name(level: int) -> str:
    """Nome temático do nível. Para níveis além da lista pré-definida,
    continua nomeando de forma amigável (mantém o último título com um
    contador extra)."""
    idx = level - 1
    if 0 <= idx < len(LEVEL_NAMES):
        return LEVEL_NAMES[idx]
    extra = level - len(LEVEL_NAMES)
    return f"{LEVEL_NAMES[-1]} {extra + 1}"


def level_xp_range(level: int) -> tuple[int, int | None]:
    """Faixa de XP (mínimo, máximo) de um nível. O último nível informado
    retorna máximo None (sem teto)."""
    minimo = (level - 1) * LEVEL_XP_STEP
    maximo = level * LEVEL_XP_STEP - 1
    return minimo, maximo


def empty_atividades_df() -> pd.DataFrame:
    return pd.DataFrame(columns=ATIVIDADES_COLUMNS)


def workbook_to_bytes(dfs: dict) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        for sheet_name, df in dfs.items():
            df.to_excel(writer, sheet_name=sheet_name, index=False)
    buffer.seek(0)
    return buffer.read()


def bytes_to_workbook(content: bytes) -> dict:
    buffer = io.BytesIO(content)
    xls = pd.ExcelFile(buffer, engine="openpyxl")
    return {sheet: xls.parse(sheet) for sheet in xls.sheet_names}


def normalize_atividades(df: pd.DataFrame) -> pd.DataFrame:
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
            if col == "MetaSemanal":
                df[col] = 14
            elif col == "IsAdmin":
                df[col] = False
            elif col == "TipoPlano":
                df[col] = "personalizado"
            elif col in ("DisponibilidadeJSON", "MateriaisJSON"):
                df[col] = "[]"
            elif col == "DuracoesPadraoJSON":
                df[col] = "{}"
            else:
                df[col] = ""
    df["MetaSemanal"] = pd.to_numeric(df["MetaSemanal"], errors="coerce").fillna(14).astype(int)
    df["SenhaHash"] = df["SenhaHash"].fillna("").astype(str)
    df["IsAdmin"] = df["IsAdmin"].apply(
        lambda v: v if isinstance(v, bool) else str(v).strip().lower() in ("true", "1", "sim", "yes")
    )
    df["TipoPlano"] = df["TipoPlano"].fillna("personalizado").astype(str)
    df["TipoPlano"] = df["TipoPlano"].replace("", "personalizado")
    df["DisponibilidadeJSON"] = df["DisponibilidadeJSON"].fillna("[]").astype(str).replace("", "[]")
    df["MateriaisJSON"] = df["MateriaisJSON"].fillna("[]").astype(str).replace("", "[]")
    df["DuracoesPadraoJSON"] = df["DuracoesPadraoJSON"].fillna("{}").astype(str).replace("", "{}")
    df = df[USUARIOS_COLUMNS]
    return ensure_admin(df)
