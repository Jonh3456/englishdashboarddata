"""
Sincronização do arquivo Excel com um repositório GitHub, usando a
Contents API (https://docs.github.com/en/rest/repos/contents).

Requer, em st.secrets (arquivo .streamlit/secrets.toml ou nas
"Secrets" do Streamlit Community Cloud):

    GITHUB_TOKEN      = "ghp_xxx..."      # Personal Access Token com escopo 'repo'
    GITHUB_REPO       = "usuario/repo"    # ex: "darlei/english-dashboard-data"
    GITHUB_BRANCH     = "main"            # opcional, default "main"
    GITHUB_FILE_PATH  = "data/estudo_ingles_dados.xlsx"  # opcional

Esta versão NORMALIZA automaticamente os valores acima para evitar o erro
422 "path contains a malformed path component" causado por barras extras,
aspas coladas, barras invertidas (Windows), URLs completas coladas por
engano ou o nome do repo duplicado dentro do path.
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


def _normalize_repo(repo: str) -> str:
    """Aceita 'usuario/repo', mas também tolera URL completa ou barras extras."""
    repo = (repo or "").strip()
    repo = repo.strip('"').strip("'")
    repo = repo.strip("/")
    for prefix in ("https://github.com/", "http://github.com/", "github.com/"):
        if repo.lower().startswith(prefix):
            repo = repo[len(prefix):]
            break
    if repo.endswith(".git"):
        repo = repo[: -len(".git")]
    return repo.strip("/")


def _normalize_path(path: str, repo: str) -> str:
    """Corrige os erros mais comuns de colagem do caminho do arquivo."""
    path = (path or "").strip()
    path = path.strip('"').strip("'")
    # se colaram uma URL completa (ex: .../blob/main/arquivo.xlsx), extrai só o caminho real
    for marker in ("/blob/main/", "/blob/master/"):
        if marker in path:
            path = path.split(marker, 1)[1]
            break
    for prefix in ("https://github.com/", "http://github.com/", "github.com/"):
        if path.lower().startswith(prefix):
            # remove domínio e, se presente, o "usuario/repo/blob/branch/"
            remainder = path[len(prefix):]
            parts = remainder.split("/")
            if len(parts) > 4 and parts[2] in ("blob", "tree"):
                path = "/".join(parts[4:])
            else:
                path = remainder
            break
    path = path.replace("\\", "/")  # barra invertida (Windows) -> barra normal
    path = path.strip("/")
    while "//" in path:
        path = path.replace("//", "/")
    # remove o nome do repositório caso tenha sido colado junto ao path por engano
    if repo and path.lower().startswith(repo.lower() + "/"):
        path = path[len(repo) + 1:]
    path = path.strip("/")
    return path


def _normalize_branch(branch: str) -> str:
    branch = (branch or "main").strip().strip('"').strip("'").strip("/")
    return branch or "main"


def _config():
    repo = _normalize_repo(_get_secret("GITHUB_REPO", ""))
    branch = _normalize_branch(_get_secret("GITHUB_BRANCH", "main"))
    raw_path = _get_secret("GITHUB_FILE_PATH", "data/estudo_ingles_dados.xlsx")
    path = _normalize_path(raw_path, repo)
    if not path:
        path = "data/estudo_ingles_dados.xlsx"
    return repo, branch, path


def get_diagnostics() -> dict:
    """Retorna os valores normalizados (sem o token) para exibir na tela de
    Configurações e ajudar a depurar problemas de path/repo."""
    repo, branch, path = _config()
    token = _get_secret("GITHUB_TOKEN", "")
    return {
        "repo": repo,
        "branch": branch,
        "path": path,
        "token_presente": bool(token),
        "token_prefixo": (token[:7] + "...") if token else "",
        "url_api": f"{API_ROOT}/repos/{repo}/contents/{path}" if repo and path else "",
    }


def _headers():
    token = _get_secret("GITHUB_TOKEN", "")
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def is_configured() -> bool:
    repo, _, path = _config()
    token = _get_secret("GITHUB_TOKEN", "")
    return bool(repo) and bool(token) and bool(path)


def fetch_file():
    """Retorna (content_bytes, sha) ou (None, None) se o arquivo não existir."""
    repo, branch, path = _config()
    if not repo or not path:
        raise RuntimeError(
            "GITHUB_REPO ou GITHUB_FILE_PATH estão vazios após a normalização. "
            "Confira as Secrets no Streamlit Cloud."
        )
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
    if not repo or not path:
        raise RuntimeError(
            "GITHUB_REPO ou GITHUB_FILE_PATH estão vazios após a normalização. "
            "Confira as Secrets no Streamlit Cloud."
        )
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
