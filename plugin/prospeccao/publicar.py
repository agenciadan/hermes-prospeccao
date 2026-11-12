import hashlib
import http.client
import json
import os
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import quote


class PublishError(Exception):
    pass


def publicar(pasta: Path, provedor: str, projeto: str) -> str:
    if provedor not in ("vercel", "cloudflare"):
        raise PublishError(f"provedor desconhecido: {provedor!r}")
    url = _enviar(Path(pasta), provedor, projeto).get("url")
    if not url:
        raise PublishError(f"{provedor}: resposta sem URL")
    return url


def _enviar(pasta: Path, provedor: str, projeto: str) -> dict:
    if not (pasta / "index.html").is_file():
        raise PublishError(f"pasta inexistente ou sem index.html: {pasta}")
    arquivos = _coletar(pasta)
    if provedor == "vercel":
        return _vercel(arquivos, projeto)
    return _cloudflare(arquivos, projeto)


def _vercel(arquivos: dict, projeto: str) -> dict:
    token = _segredo("VERCEL_TOKEN")
    arquivos_api = []
    for caminho, dados in arquivos.items():
        sha = hashlib.sha1(dados).hexdigest()
        _http("POST", "https://api.vercel.com/v2/files", token, dados,
              {"Content-Type": "application/octet-stream", "x-vercel-digest": sha})
        arquivos_api.append({"file": caminho, "sha": sha, "size": len(dados)})
    corpo = json.dumps({"name": projeto, "files": arquivos_api}).encode()
    resp = _json(_http("POST", "https://api.vercel.com/v13/deployments", token, corpo,
                       {"Content-Type": "application/json"}))
    url = resp.get("url")
    return {"url": f"https://{url}" if url else None}


def _cloudflare(arquivos: dict, projeto: str) -> dict:
    token = _segredo("CLOUDFLARE_API_TOKEN")
    conta = _segredo("CLOUDFLARE_ACCOUNT_ID")
    manifesto, blobs = {}, {}
    for caminho, dados in arquivos.items():
        h = hashlib.sha256(dados).hexdigest()
        manifesto["/" + caminho] = h
        blobs[h] = dados  # conteúdo repetido vira uma parte só
    corpo, tipo = _multipart(json.dumps(manifesto), blobs)
    url = (f"https://api.cloudflare.com/client/v4/accounts/{quote(conta, safe='')}"
           f"/pages/projects/{quote(projeto, safe='')}/deployments")
    resp = _json(_http("POST", url, token, corpo, {"Content-Type": tipo}))
    if not resp.get("success"):
        raise PublishError(f"cloudflare: {resp.get('errors')}")
    return {"url": (resp.get("result") or {}).get("url")}


def _multipart(manifesto: str, blobs: dict) -> tuple[bytes, str]:
    fronteira = uuid.uuid4().hex
    corpo = bytearray()
    corpo += (f"--{fronteira}\r\nContent-Disposition: form-data; name=\"manifest\"\r\n\r\n"
              f"{manifesto}\r\n").encode()
    for h, dados in blobs.items():
        corpo += (f"--{fronteira}\r\nContent-Disposition: form-data; name=\"{h}\"; filename=\"{h}\"\r\n"
                  f"Content-Type: application/octet-stream\r\n\r\n").encode() + dados + b"\r\n"
    corpo += f"--{fronteira}--\r\n".encode()
    return bytes(corpo), f"multipart/form-data; boundary={fronteira}"


def _coletar(pasta: Path) -> dict:
    # symlink fica de fora (link para arquivo local vazaria); dotfiles e pastas ocultas (.env, .git) também
    arquivos = {}
    for p in sorted(pasta.rglob("*")):
        rel = p.relative_to(pasta)
        if p.is_file() and not p.is_symlink() and not any(parte.startswith(".") for parte in rel.parts):
            arquivos[rel.as_posix()] = p.read_bytes()
    return arquivos


def _segredo(nome: str) -> str:
    valor = os.environ.get(nome)
    env = Path.home() / ".hermes" / ".env"
    if not valor and env.is_file():
        try:
            linhas = env.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError):  # sem citar o conteúdo: o erro pode trazer bytes do segredo
            raise PublishError(f"não foi possível ler {env}") from None
        for linha in linhas:
            chave, sep, bruto = linha.strip().removeprefix("export ").partition("=")
            if sep and chave.strip() == nome:
                valor = bruto.strip().strip("'\"")
    if not valor:
        raise PublishError(f"{nome} ausente: defina no ambiente ou em ~/.hermes/.env")
    return valor


def _http(metodo: str, url: str, token: str, corpo: bytes, cabecalhos: dict) -> bytes:
    req = urllib.request.Request(url, data=corpo, method=metodo,
                                 headers={**cabecalhos, "Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.read()
    except urllib.error.HTTPError as e:  # corpo de erro pode ecoar o token: nunca sai na mensagem (R38)
        corpo_erro = e.read()[:300].decode("utf-8", "replace").replace(token, "***")
        raise PublishError(f"HTTP {e.code} em {url}: {corpo_erro}") from None
    except (OSError, http.client.HTTPException) as e:  # URLError e timeout são OSError
        raise PublishError(f"falha de rede em {url}: {str(e).replace(token, '***')}") from None


def _json(raw: bytes) -> dict:
    try:
        dado = json.loads(raw)
    except ValueError:
        dado = None
    if not isinstance(dado, dict):
        raise PublishError("resposta não é um objeto JSON")
    return dado
