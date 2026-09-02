"""
Sincronização do arquivo de dados (Excel) com um repositório do GitHub,
usando a API REST de Conteúdo (Contents API). Cada gravação vira um commit.

Secrets esperados (em .streamlit/secrets.toml local, ou em
"Settings -> Secrets" no Streamlit Community Cloud), como CHAVES SOLTAS
(não use uma tabela [github] — use exatamente estes nomes):

    GITHUB_TOKEN = "ghp_xxx"                          # obrigatório
    GITHUB_REPO = "seu-usuario/seu-repositorio"        # obrigatório
    GITHUB_BRANCH = "main"                             # opcional (padrão: "main")
    GITHUB_FILE_PATH = "data/estudo_ingles_dados.xlsx"  # opcional (padrão abaixo)
"""
from __future__ import annotations

import base64

import requests
import streamlit as st

API = "https://api.github.com"
DEFAULT_BRANCH = "main"
DEFAULT_FILE_PATH = "data/estudo_ingles_dados.xlsx"


def _secret(key: str, default=None):
    try:
        value = st.secrets[key]
        return value if value else default
    except Exception:
        return default


def is_configured() -> bool:
    return bool(_secret("GITHUB_TOKEN")) and bool(_secret("GITHUB_REPO"))


def _headers() -> dict:
    return {
        "Authorization": f"token {_secret('GITHUB_TOKEN')}",
        "Accept": "application/vnd.github+json",
    }


def _repo() -> str:
    return _secret("GITHUB_REPO")


def _branch() -> str:
    return _secret("GITHUB_BRANCH", DEFAULT_BRANCH)


def _path() -> str:
    return _secret("GITHUB_FILE_PATH", DEFAULT_FILE_PATH)


def fetch_file():
    """Retorna (bytes_do_arquivo, sha) ou (None, None) se ainda não existir no repositório."""
    url = f"{API}/repos/{_repo()}/contents/{_path()}"
    resp = requests.get(url, headers=_headers(), params={"ref": _branch()}, timeout=20)
    if resp.status_code == 200:
        payload = resp.json()
        return base64.b64decode(payload["content"]), payload["sha"]
    if resp.status_code == 404:
        return None, None
    raise RuntimeError(f"Erro ao buscar arquivo no GitHub ({resp.status_code}): {resp.text}")


def push_file(content: bytes, sha, message: str) -> str:
    """Grava (cria ou atualiza) o arquivo no repositório. Retorna o novo sha."""
    url = f"{API}/repos/{_repo()}/contents/{_path()}"
    payload = {
        "message": message,
        "content": base64.b64encode(content).decode("utf-8"),
        "branch": _branch(),
    }
    if sha:
        payload["sha"] = sha
    resp = requests.put(url, headers=_headers(), json=payload, timeout=30)
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"Erro ao salvar no GitHub ({resp.status_code}): {resp.text}")
    return resp.json()["content"]["sha"]
