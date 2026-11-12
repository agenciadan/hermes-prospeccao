import hashlib
import http.client
import importlib
import io
import json
import urllib.error
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "plugin"


@pytest.fixture
def mod(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(PLUGIN_ROOT))  # restaurado ao fim do teste
    monkeypatch.setenv("HOME", str(tmp_path / "casa"))  # isola ~/.hermes/.env
    for nome in ("VERCEL_TOKEN", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"):
        monkeypatch.delenv(nome, raising=False)
    return importlib.import_module("prospeccao.publicar")


@pytest.fixture
def pasta(tmp_path):
    site = tmp_path / "site"
    (site / "refs").mkdir(parents=True)
    (site / "index.html").write_text("<h1>x</h1>")
    (site / "refs" / "a.txt").write_text("ref")
    return site


def test_sucesso_retorna_url(mod, monkeypatch, pasta):
    monkeypatch.setattr(mod, "_enviar", lambda *a: {"url": "https://x.vercel.app"})
    assert mod.publicar(pasta, "vercel", "x") == "https://x.vercel.app"


def test_falha_levanta_erro(mod, monkeypatch, pasta):
    def falha(*a):
        raise mod.PublishError("500")

    monkeypatch.setattr(mod, "_enviar", falha)
    with pytest.raises(mod.PublishError):
        mod.publicar(pasta, "cloudflare", "x")


def test_resposta_sem_url_levanta_erro(mod, monkeypatch, pasta):
    monkeypatch.setattr(mod, "_enviar", lambda *a: {})
    with pytest.raises(mod.PublishError, match="sem URL"):
        mod.publicar(pasta, "vercel", "x")


def test_provedor_desconhecido_nao_envia(mod, monkeypatch, pasta):
    monkeypatch.setattr(mod, "_enviar", lambda *a: pytest.fail("não deveria enviar"))
    with pytest.raises(mod.PublishError, match="desconhecido"):
        mod.publicar(pasta, "netlify", "x")


def test_pasta_sem_index_falha_antes_do_envio(mod, monkeypatch, tmp_path):
    monkeypatch.setattr(mod, "_http", lambda *a: pytest.fail("não deveria enviar"))
    with pytest.raises(mod.PublishError, match="index.html"):
        mod.publicar(tmp_path, "vercel", "x")
    with pytest.raises(mod.PublishError, match="index.html"):
        mod.publicar(tmp_path / "nao-existe", "vercel", "x")


@pytest.mark.parametrize("provedor, ambiente, nome", [
    ("vercel", {}, "VERCEL_TOKEN"),
    ("cloudflare", {}, "CLOUDFLARE_API_TOKEN"),
    ("cloudflare", {"CLOUDFLARE_API_TOKEN": "tok-secreto"}, "CLOUDFLARE_ACCOUNT_ID"),
])
def test_credencial_ausente_cita_so_o_nome(mod, monkeypatch, pasta, provedor, ambiente, nome):
    for chave, valor in ambiente.items():
        monkeypatch.setenv(chave, valor)
    monkeypatch.setattr(mod, "_http", lambda *a: pytest.fail("não deveria enviar"))
    with pytest.raises(mod.PublishError) as erro:
        mod.publicar(pasta, provedor, "x")
    assert nome in str(erro.value)
    assert "tok-secreto" not in str(erro.value)


def test_segredo_le_hermes_env(mod, monkeypatch, tmp_path):
    env = tmp_path / "casa" / ".hermes" / ".env"
    env.parent.mkdir(parents=True)
    env.write_text("# comentario\nVERCEL_TOKEN='tok-arquivo'\n")
    assert mod._segredo("VERCEL_TOKEN") == "tok-arquivo"


def test_vercel_envia_arquivos_e_monta_url(mod, monkeypatch, pasta):
    monkeypatch.setenv("VERCEL_TOKEN", "tok-teste")
    chamadas = []

    def http(metodo, url, token, corpo, cab):
        chamadas.append((url, token, corpo, cab))
        if url.endswith("/v13/deployments"):
            return b'{"url": "x-abc.vercel.app"}'
        return b""

    monkeypatch.setattr(mod, "_http", http)
    assert mod.publicar(pasta, "vercel", "x") == "https://x-abc.vercel.app"

    uploads = [c for c in chamadas if c[0].endswith("/v2/files")]
    assert {c[3]["x-vercel-digest"] for c in uploads} == {
        hashlib.sha1(b"<h1>x</h1>").hexdigest(), hashlib.sha1(b"ref").hexdigest()}
    deploy = json.loads(chamadas[-1][2])
    assert {f["file"]: f["sha"] for f in deploy["files"]} == {
        "index.html": hashlib.sha1(b"<h1>x</h1>").hexdigest(),
        "refs/a.txt": hashlib.sha1(b"ref").hexdigest()}
    assert {c[1] for c in chamadas} == {"tok-teste"}


def test_cloudflare_monta_multipart_e_url(mod, monkeypatch, pasta):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "tok-cf")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "conta123")
    chamadas = []

    def http(metodo, url, token, corpo, cab):
        chamadas.append((url, token, corpo, cab))
        return json.dumps({"success": True, "result": {"url": "https://h.x.pages.dev"}}).encode()

    monkeypatch.setattr(mod, "_http", http)
    assert mod.publicar(pasta, "cloudflare", "x") == "https://h.x.pages.dev"

    url, token, corpo, cab = chamadas[0]
    assert url == "https://api.cloudflare.com/client/v4/accounts/conta123/pages/projects/x/deployments"
    assert token == "tok-cf"
    assert cab["Content-Type"].startswith("multipart/form-data; boundary=")
    assert b'"/index.html"' in corpo and b"<h1>x</h1>" in corpo


def test_http_erro_e_rede_viram_publish_error(mod, monkeypatch):
    def http_500(*a, **k):
        raise urllib.error.HTTPError("u", 500, "boom", {}, io.BytesIO(b"erro do servico"))

    monkeypatch.setattr(mod.urllib.request, "urlopen", http_500)
    with pytest.raises(mod.PublishError, match="HTTP 500"):
        mod._http("POST", "https://api.vercel.com/v2/files", "tok", b"", {})

    def sem_rede(*a, **k):
        raise urllib.error.URLError("sem rota")

    monkeypatch.setattr(mod.urllib.request, "urlopen", sem_rede)
    with pytest.raises(mod.PublishError, match="rede"):
        mod._http("POST", "https://api.vercel.com/v2/files", "tok", b"", {})


def test_resposta_nao_json_vira_publish_error(mod, monkeypatch, pasta):
    monkeypatch.setenv("VERCEL_TOKEN", "tok")
    monkeypatch.setattr(mod, "_http", lambda *a: b"<html>")
    with pytest.raises(mod.PublishError):
        mod.publicar(pasta, "vercel", "x")


def test_nao_publica_symlink_nem_pasta_linkada(mod, tmp_path, pasta):
    fora = tmp_path / "fora"
    fora.mkdir()
    (fora / "segredo.txt").write_text("chave")
    (pasta / "vaza.txt").symlink_to(fora / "segredo.txt")
    (pasta / "pasta_link").symlink_to(fora)
    coletados = mod._coletar(pasta)
    assert set(coletados) == {"index.html", "refs/a.txt"}
