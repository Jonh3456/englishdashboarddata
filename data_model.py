"""
Módulo de dados: estrutura do Excel, template do plano de 6 meses,
geração de plano PERSONALIZADO (disponibilidade + materiais escolhidos
por cada pessoa), usuários padrão (com login por PIN) e helpers de
leitura/escrita em memória (BytesIO).

IMPORTANTE: cada pessoa tem seu próprio período de 6 meses, que começa
no dia em que ela cria sua conta (não em uma data fixa do projeto) —
ver add_months() e os parâmetros start_date/end_date em
build_template_activities / build_personalized_activities.
"""
from __future__ import annotations

import calendar
import hashlib
import io
from datetime import date, timedelta

import pandas as pd

# ============================================================
# CONSTANTES GERAIS (usadas apenas como padrão do usuário-semente,
# criado automaticamente na primeiríssima execução do app)
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

USER_PALETTE = ["#2563eb", "#f97316", "#10b981", "#e11d48", "#a855f7", "#0ea5e9"]

WEEKDAY_NAMES = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

ATIVIDADES_COLUMNS = [
    "ID", "Usuario", "Data", "Horario", "Tarefa", "Habilidade", "Modalidade",
    "MinutosPlanejados", "MinutosExecutados", "Concluido", "Anotacoes", "DataConclusao",
]

# Coluna "SenhaHash" guarda o PIN/senha do usuário já com hash (nunca em texto puro)
# Coluna "IsAdmin" identifica quem pode acessar o Modo Admin (gerenciar outras pessoas).
USUARIOS_COLUMNS = ["Usuario", "Equipe", "Cor", "MetaSemanal", "SenhaHash", "IsAdmin"]

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

# Duração PADRÃO sugerida (em minutos) para cada material do catálogo acima.
# Usada quando a pessoa escolhe "Tempo padrão" ao criar a conta. Se a pessoa
# escolher "Tempo personalizável", esses valores servem apenas como ponto de
# partida — ela pode alterar cada um livremente antes de gerar o calendário.
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

DEFAULT_CUSTOM_MATERIAL_DURATION = 30  # fallback para materiais adicionados manualmente pela pessoa


def get_default_duration(nome_material: str) -> int:
    """Duração padrão (minutos) de um material/tarefa. Cai para um valor
    genérico se o material não estiver no catálogo (ex: material customizado
    criado pela própria pessoa, ou nome de tarefa do template clássico)."""
    return DEFAULT_MATERIAL_DURATIONS.get(nome_material, DEFAULT_CUSTOM_MATERIAL_DURATION)


def list_template_task_names() -> list[str]:
    """Lista (sem repetição, na ordem em que aparecem) todas as tarefas do
    template semanal clássico — usada para montar a tabela de personalização
    de tempo quando a pessoa escolhe o modelo padrão."""
    vistos: list[str] = []
    for _, itens in sorted(WEEKLY_TEMPLATE.items()):
        for item in itens:
            if item["Tarefa"] not in vistos:
                vistos.append(item["Tarefa"])
    return vistos


def template_task_default_duration(nome_tarefa: str) -> int:
    """Duração padrão (minutos) de uma tarefa do template clássico, lida
    diretamente do WEEKLY_TEMPLATE (primeira ocorrência encontrada)."""
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
    {"Dia": "Sábado", "Horario": "10:00", "Minutos": 120},
    {"Dia": "Domingo", "Horario": "15:00", "Minutos": 60},
]

# Template semanal padrão: 0=Segunda ... 6=Domingo (igual a date.weekday())
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
# LOGIN / SENHA
# ============================================================
def hash_password(raw: str) -> str:
    """Gera um hash SHA-256 simples do PIN/senha (nunca guardamos texto puro)."""
    return hashlib.sha256((raw or "").encode("utf-8")).hexdigest()


# ============================================================
# GERAÇÃO DO PLANO PADRÃO (MODELO CLÁSSICO)
# ============================================================
def build_template_activities(
    usuario: str,
    start_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    custom_durations: dict[str, int] | None = None,
) -> pd.DataFrame:
    """Gera o plano de 6 meses seguindo o template semanal padrão.

    Se start_date/end_date não forem informados, usa a janela padrão do
    projeto (START_DATE/END_DATE) — usado apenas para o usuário-semente.
    Ao criar uma NOVA pessoa pela tela de login, o app.py sempre passa
    start_date=hoje e end_date=hoje+6 meses.

    custom_durations: dict opcional {nome_da_tarefa: minutos}. Quando a
    pessoa escolhe "Tempo personalizável" na tela de criação de conta, os
    valores aqui substituem a duração padrão daquela tarefa (item do
    WEEKLY_TEMPLATE). Se omitido, usa sempre a duração padrão do template
    (comportamento idêntico ao anterior).
    """
    start_date = start_date or START_DATE
    end_date = end_date or END_DATE
    custom_durations = custom_durations or {}

    rows = []
    cursor = start_date
    next_id = start_id
    while cursor <= end_date:
        weekday = cursor.weekday()  # 0=Monday
        for item in WEEKLY_TEMPLATE.get(weekday, []):
            duracao = custom_durations.get(item["Tarefa"], item["MinutosPlanejados"])
            rows.append({
                "ID": next_id,
                "Usuario": usuario,
                "Data": cursor.isoformat(),
                "Horario": item["Horario"],
                "Tarefa": item["Tarefa"],
                "Habilidade": item["Habilidade"],
                "Modalidade": item["Modalidade"],
                "MinutosPlanejados": int(duracao),
                "MinutosExecutados": 0,
                "Concluido": False,
                "Anotacoes": "",
                "DataConclusao": "",
            })
            next_id += 1
        cursor += timedelta(days=1)
    return pd.DataFrame(rows, columns=ATIVIDADES_COLUMNS)


# ============================================================
# GERAÇÃO DO PLANO PERSONALIZADO
# ============================================================
def _resolve_material_durations(materiais: list[dict], material_durations: dict[str, int] | None) -> dict[str, int]:
    """Resolve a duração efetiva (minutos) de cada material: usa o valor
    personalizado se informado, senão cai para a duração padrão do catálogo
    (ou o fallback genérico, se o material não estiver no catálogo)."""
    material_durations = material_durations or {}
    resolvidas = {}
    for m in materiais:
        nome = m["nome"]
        resolvidas[nome] = int(material_durations.get(nome) or get_default_duration(nome))
    return resolvidas


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
    materiais: [{"nome": str, "habilidade": str}, ...] — usados em rodízio (round-robin)
               ao longo do período, na ordem em que a pessoa escolheu.
    start_date/end_date: janela do plano desta pessoa. Se omitidos, usa a
        janela padrão do projeto (START_DATE/END_DATE).
    material_durations: dict opcional {nome_do_material: minutos}. Define a
        duração de CADA sessão daquele material. Se omitido (ou se um
        material específico não estiver no dict), usa a duração padrão do
        catálogo (get_default_duration).

    ESTRATÉGIA DE DISTRIBUIÇÃO ("empacotamento"/bin-packing):
    Dentro de cada bloco de disponibilidade, o rodízio de materiais é
    empacotado em sequência — várias sessões de materiais diferentes cabem
    no MESMO bloco, uma atrás da outra, até que a soma delas se aproxime o
    máximo possível do tempo disponível naquele bloco. Quando o próximo
    material da vez (na ordem do rodízio) não couber mais no tempo restante
    daquele bloco, a distribuição PARA de preencher esse bloco (o tempo
    restante fica ocioso ali) e o rodízio AVANÇA para o próximo bloco
    disponível (não reinicia do zero) — ou seja, esse mesmo material fica
    "guardado" para começar o próximo bloco livre, garantindo que nenhuma
    sessão seja cortada pela metade.
    """
    start_date = start_date or START_DATE
    end_date = end_date or END_DATE

    if not materiais:
        materiais = [{"nome": "Estudo livre", "habilidade": s} for s in SKILLS]

    duracoes = _resolve_material_durations(materiais, material_durations)
    n = len(materiais)
    MAX_FRAGMENTOS_POR_BLOCO = 20  # trava de segurança contra loops longos demais

    rows = []
    cursor = start_date
    next_id = start_id
    rot_idx = 0  # posição do rodízio — contínua entre blocos/dias, nunca reinicia

    while cursor <= end_date:
        blocos = disponibilidade.get(cursor.weekday(), [])
        blocos_ordenados = sorted(blocos, key=lambda b: str(b.get("horario", "")))
        for bloco in blocos_ordenados:
            minutos_disponiveis = int(bloco.get("minutos", 0) or 0)
            if minutos_disponiveis <= 0:
                continue
            horario = str(bloco.get("horario", "18:00"))
            restante = minutos_disponiveis
            fragmentos = 0

            # Empacota quantas sessões couberem neste bloco, em sequência.
            while restante > 0 and fragmentos < MAX_FRAGMENTOS_POR_BLOCO:
                material = materiais[rot_idx % n]
                duracao = duracoes[material["nome"]]
                if duracao > restante:
                    # Não força sessão cortada: fecha este bloco (tempo
                    # restante fica ocioso) e deixa este material para o
                    # próximo bloco livre (rot_idx não avança).
                    break
                rows.append({
                    "ID": next_id,
                    "Usuario": usuario,
                    "Data": cursor.isoformat(),
                    "Horario": horario,
                    "Tarefa": material["nome"],
                    "Habilidade": material["habilidade"],
                    "Modalidade": "Personalizado",
                    "MinutosPlanejados": duracao,
                    "MinutosExecutados": 0,
                    "Concluido": False,
                    "Anotacoes": "",
                    "DataConclusao": "",
                })
                next_id += 1
                restante -= duracao
                rot_idx += 1
                fragmentos += 1
        cursor += timedelta(days=1)
    return pd.DataFrame(rows, columns=ATIVIDADES_COLUMNS)


# ============================================================
# CÁLCULO DE "CICLOS COMPLETOS" DE MATERIAIS AO LONGO DO PERÍODO
# ============================================================
def compute_material_cycles(
    disponibilidade: dict[int, list[dict]],
    materiais: list[dict],
    start_date: date,
    end_date: date,
    material_durations: dict[str, int] | None = None,
) -> dict:
    """
    Calcula quantos "ciclos completos" (uma rodada passando por TODOS os
    materiais uma vez cada) cabem ao longo do período todo, considerando a
    disponibilidade semanal informada.

    Regra de "fechamento" do resumo:
      - Se um ciclo completo cabe dentro de 1 semana (ou menos), o resumo é
        fechado por SEMANA (quantos ciclos completos cabem por semana).
      - Se um ciclo completo precisa de mais de 1 semana para se completar,
        o resumo é fechado por MÊS (quantos ciclos completos cabem por mês).

    Retorna um dict com as métricas already calculadas, prontas para exibir
    na tela (ex: flash de boas-vindas após criar a conta).
    """
    if not materiais:
        return {
            "cycle_minutes": 0, "weekly_capacity_min": 0, "total_capacity_min": 0,
            "complete_cycles_in_period": 0, "fechamento": "semanal",
            "cycles_per_week": 0.0, "cycles_per_month": 0.0, "weeks_per_cycle": 0.0,
            "materiais_sem_encaixe": [],
        }

    duracoes = _resolve_material_durations(materiais, material_durations)
    cycle_minutes = sum(duracoes.values())

    weekly_capacity_min = weekly_minutes_from_availability(disponibilidade)

    # Capacidade total do período inteiro (soma de todos os blocos, dia a dia).
    total_capacity_min = 0
    cursor = start_date
    while cursor <= end_date:
        for bloco in disponibilidade.get(cursor.weekday(), []):
            total_capacity_min += int(bloco.get("minutos", 0) or 0)
        cursor += timedelta(days=1)

    # Materiais cuja duração nunca cabe em NENHUM bloco cadastrado (aviso).
    maiores_blocos_por_dia = [
        max((int(b.get("minutos", 0) or 0) for b in blocos), default=0)
        for blocos in disponibilidade.values()
    ]
    maior_bloco_existente = max(maiores_blocos_por_dia, default=0)
    materiais_sem_encaixe = [
        nome for nome, dur in duracoes.items() if dur > maior_bloco_existente
    ]

    complete_cycles_in_period = (total_capacity_min // cycle_minutes) if cycle_minutes else 0
    weeks_per_cycle = (cycle_minutes / weekly_capacity_min) if weekly_capacity_min else float("inf")

    if weeks_per_cycle <= 1:
        fechamento = "semanal"
        cycles_per_week = round((weekly_capacity_min / cycle_minutes), 2) if cycle_minutes else 0.0
        cycles_per_month = round(cycles_per_week * 4.345, 2)
    else:
        fechamento = "mensal"
        cycles_per_week = round(1 / weeks_per_cycle, 3) if weeks_per_cycle else 0.0
        weeks_per_month = 4.345
        cycles_per_month = round(weeks_per_month / weeks_per_cycle, 2) if weeks_per_cycle else 0.0

    return {
        "cycle_minutes": cycle_minutes,
        "weekly_capacity_min": weekly_capacity_min,
        "total_capacity_min": total_capacity_min,
        "complete_cycles_in_period": int(complete_cycles_in_period),
        "fechamento": fechamento,
        "cycles_per_week": cycles_per_week,
        "cycles_per_month": cycles_per_month,
        "weeks_per_cycle": round(weeks_per_cycle, 2) if weeks_per_cycle != float("inf") else None,
        "materiais_sem_encaixe": materiais_sem_encaixe,
    }


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
# DATAFRAMES VAZIOS / PADRÃO
# ============================================================
def default_usuarios_df() -> pd.DataFrame:
    return pd.DataFrame(
        [{"Usuario": "Darlei", "Equipe": "Time Fluência", "Cor": USER_PALETTE[0],
          "MetaSemanal": 14, "SenhaHash": "", "IsAdmin": True}],
        columns=USUARIOS_COLUMNS,
    )


def ensure_admin(usuarios: pd.DataFrame) -> pd.DataFrame:
    """Garante que sempre exista ao menos 1 administrador.

    Se, por qualquer motivo (dados antigos sem a coluna, remoção/rebaixamento
    do último admin, etc.), ninguém estiver marcado como admin, promove
    automaticamente a primeira pessoa cadastrada — assim o app nunca fica
    "órfão" de Modo Admin.
    """
    if usuarios.empty:
        return usuarios
    usuarios = usuarios.copy()
    if not usuarios["IsAdmin"].any():
        usuarios.iloc[0, usuarios.columns.get_loc("IsAdmin")] = True
    return usuarios


def empty_atividades_df() -> pd.DataFrame:
    return pd.DataFrame(columns=ATIVIDADES_COLUMNS)


# ============================================================
# (DE)SERIALIZAÇÃO EXCEL
# ============================================================
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


# ============================================================
# NORMALIZAÇÃO (garante colunas/tipos corretos ao carregar do Excel)
# ============================================================
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
            if col == "MetaSemanal":
                df[col] = 14
            elif col == "IsAdmin":
                df[col] = False
            else:
                df[col] = ""
    df["MetaSemanal"] = pd.to_numeric(df["MetaSemanal"], errors="coerce").fillna(14).astype(int)
    df["SenhaHash"] = df["SenhaHash"].fillna("").astype(str)
    df["IsAdmin"] = df["IsAdmin"].apply(lambda v: str(v).strip().lower() in ("true", "1", "sim", "yes"))
    df = ensure_admin(df)
    return df[USUARIOS_COLUMNS]
