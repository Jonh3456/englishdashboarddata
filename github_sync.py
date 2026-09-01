"""
Sincronização do arquivo Excel com um repositório GitHub, usando a
Contents API (https://docs.github.com/en/rest/repos/contents).

Requer, em st.secrets (arquivo .streamlit/secrets.toml ou nas
"Secrets" do Streamlit Community Cloud):

    GITHUB_TOKEN      = "ghp_xxx..."      # Personal Access Token com escopo 'repo'
    GITHUB_REPO       = "usuario/repo"    # ex: "darlei/english-dashboard-data"
    GITHUB_BRANCH     = "main"            # opcional, default "main"
    GITHUB_FILE_PATH  = "data/estudo_ingles_dados.xlsx"  # opcional
"""
import base64
import time
import requests
import streamlit as st

API_ROOT = "https://api.github.com"


def _get_secret(key: str, default: str = "") -> str:
    """Lê st.secrets com segurança, mesmo quando nenhum secrets.toml existe."""
    try:
        return st.secrets.get(key, default)
    except Exception:  # noqa: BLE001 - StreamlitSecretNotFoundError e afins
        return default


def _headers():
    token = _get_secret("GITHUB_TOKEN", "")
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _config():
    repo = _get_secret("GITHUB_REPO", "")
    branch = _get_secret("GITHUB_BRANCH", "main")
    path = _get_secret("GITHUB_FILE_PATH", "data/estudo_ingles_dados.xlsx")
    return repo, branch, path


def is_configured() -> bool:
    repo, _, _ = _config()
    token = _get_secret("GITHUB_TOKEN", "")
    return bool(repo) and bool(token)


def fetch_file():
    """Retorna (content_bytes, sha) ou (None, None) se o arquivo não existir."""
    repo, branch, path = _config()
    url = f"{API_ROOT}/repos/{repo}/contents/{path}"
    resp = requests.get(url, headers=_headers(), params={"ref": branch}, timeout=20)
    if resp.status_code == 200:
        payload = resp.json()
        content = base64.b64decode(payload["content"])
        return content, payload["sha"]
    if resp.status_code == 404:
        return None, None
    raise RuntimeError(f"Erro ao ler arquivo no GitHub ({resp.status_code}): {resp.text[:300]}")


def push_file(content: bytes, sha: str | None, message: str) -> str:
    """Cria ou atualiza o arquivo no GitHub. Retorna o novo sha."""
    repo, branch, path = _config()
    url = f"{API_ROOT}/repos/{repo}/contents/{path}"
    body = {
        "message": message,
        "content": base64.b64encode(content).decode("utf-8"),
        "branch": branch,
    }
    if sha:
        body["sha"] = sha

    for attempt in range(3):
        resp = requests.put(url, headers=_headers(), json=body, timeout=30)
        if resp.status_code in (200, 201):
            return resp.json()["content"]["sha"]
        if resp.status_code == 409 and attempt < 2:
            # conflito de sha (outra pessoa salvou ao mesmo tempo) -> busca sha atual e tenta de novo
            _, latest_sha = fetch_file()
            body["sha"] = latest_sha
            time.sleep(0.6)
            continue
        raise RuntimeError(f"Erro ao salvar arquivo no GitHub ({resp.status_code}): {resp.text[:300]}")
    raise RuntimeError("Não foi possível salvar no GitHub após múltiplas tentativas (conflito de versão).")
