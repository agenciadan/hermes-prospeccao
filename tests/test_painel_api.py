import importlib.util
import socket
import urllib.request
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
API_FILE = REPO_ROOT / "plugin" / "dashboard" / "plugin_api.py"
TOKEN = "TOKEN_SECRETO_123"


@pytest.fixture
def api(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path / "casa"))  # isola ~/.hermes/.env
    for nome in ("VERCEL_TOKEN", "CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID", "GOSOM_URL"):
        monkeypatch.delenv(nome, raising=False)
    spec = importlib.util.spec_from_file_location("prospeccao_plugin_api", API_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.DB = tmp_path / "leads.db"
    mod.CONFIG = tmp_path / "config.json"
    mod.SITES = tmp_path / "sites"
    return mod


@pytest.fixture
def cliente(api):
    app = FastAPI()
    app.include_router(api.router)
    return TestClient(app)


def _semear(api, *leads):
    api.store.init_db(api.DB)
    api.store.upsert_leads(api.DB, list(leads))


def test_busca_sem_confirmar_400_e_nao_chama_gosom(cliente, api, monkeypatch):
    chamadas = []
    monkeypatch.setattr(api.busca, "buscar", lambda *a, **k: chamadas.append(a) or [])
    r = cliente.post("/busca", json={"nicho": "encanador", "cidade": "Vitória", "lat": -20.3, "lon": -40.3})
    assert r.status_code == 400
    assert chamadas == []


def test_busca_com_confirmar_grava_leads(cliente, api, monkeypatch):
    leads = [{"place_id": "p1", "nome": "Ana", "nicho": "encanador", "cidade": "Vitória", "fonte": "gosom"}]
    monkeypatch.setattr(api.busca, "buscar", lambda *a, **k: leads)
    r = cliente.post("/busca", json={"nicho": "encanador", "cidade": "Vitória",
                                     "lat": -20.3, "lon": -40.3, "confirmar": True})
    assert r.status_code == 200
    assert r.json() == {"gravados": 1}
    assert [lead["place_id"] for lead in cliente.get("/leads").json()] == ["p1"]


def test_busca_erro_do_gosom_vira_502(cliente, api, monkeypatch):
    def falha(*a, **k):
        raise api.busca.SourceError("gosom: job 1 terminou com status failed")

    monkeypatch.setattr(api.busca, "buscar", falha)
    r = cliente.post("/busca", json={"nicho": "encanador", "cidade": "Vitória",
                                     "lat": -20.3, "lon": -40.3, "confirmar": True})
    assert r.status_code == 502


def test_site_sem_confirmar_400_e_nao_gera(cliente, api, monkeypatch):
    _semear(api, {"place_id": "p1", "nome": "Ana"})
    chamadas = []
    monkeypatch.setattr(api.site, "gerar_site", lambda *a, **k: chamadas.append(a))
    r = cliente.post("/site", json={"place_id": "p1"})
    assert r.status_code == 400
    assert chamadas == []


def test_site_lead_inexistente_404(cliente):
    r = cliente.post("/site", json={"place_id": "nao-existe", "confirmar": True})
    assert r.status_code == 404


def test_publicar_sem_confirmar_400_e_nao_envia(cliente, api, monkeypatch):
    _semear(api, {"place_id": "p1", "nome": "Ana"})
    chamadas = []
    monkeypatch.setattr(api.publicar, "publicar", lambda *a, **k: chamadas.append(a))
    r = cliente.post("/publicar", json={"place_id": "p1", "provedor": "vercel"})
    assert r.status_code == 400
    assert chamadas == []


def test_publicar_provedor_invalido_400_e_nao_envia(cliente, api, monkeypatch):
    _semear(api, {"place_id": "p1", "nome": "Ana"})
    chamadas = []
    monkeypatch.setattr(api.publicar, "publicar", lambda *a, **k: chamadas.append(a))
    r = cliente.post("/publicar", json={"place_id": "p1", "provedor": "netlify", "confirmar": True})
    assert r.status_code == 400
    assert chamadas == []


def test_publicar_com_confirmar_retorna_url(cliente, api, monkeypatch):
    _semear(api, {"place_id": "p1", "nome": "Ana"})
    monkeypatch.setattr(api.publicar, "publicar", lambda *a, **k: "https://ana.vercel.app")
    r = cliente.post("/publicar", json={"place_id": "p1", "provedor": "vercel", "confirmar": True})
    assert r.status_code == 200
    assert r.json() == {"url": "https://ana.vercel.app"}


def test_token_nao_vaza_quando_publicacao_falha(cliente, api, monkeypatch):
    monkeypatch.setenv("VERCEL_TOKEN", TOKEN)
    _semear(api, {"place_id": "p1", "nome": "Ana"})

    def falha(*a, **k):  # simula módulo que ecoa o token na mensagem
        raise api.publicar.PublishError(f"HTTP 401 em https://api.vercel.com: token {TOKEN}")

    monkeypatch.setattr(api.publicar, "publicar", falha)
    r = cliente.post("/publicar", json={"place_id": "p1", "provedor": "vercel", "confirmar": True})
    assert r.status_code == 502
    assert TOKEN not in r.text


def test_get_config_retorna_defaults(cliente):
    r = cliente.get("/config")
    assert r.status_code == 200
    dados = r.json()
    assert set(dados) == {"canal_padrao", "remetente_email", "assunto_padrao",
                          "modelo_mensagem", "publicar_provedor_padrao"}
    assert dados["canal_padrao"] == "email"
    assert dados["publicar_provedor_padrao"] == "vercel"


def test_put_config_canal_invalido_400_e_arquivo_intacto(cliente, api):
    assert cliente.put("/config", json={"canal_padrao": "email"}).status_code == 200
    antes = api.CONFIG.read_bytes()
    r = cliente.put("/config", json={"canal_padrao": "sms"})
    assert r.status_code == 400
    assert api.CONFIG.read_bytes() == antes


def test_put_config_rejeita_segredo_e_aceita_nome_de_variavel(cliente, api, monkeypatch):
    monkeypatch.setenv("VERCEL_TOKEN", TOKEN)
    assert cliente.put("/config", json={"modelo_mensagem": f"use {TOKEN} aqui"}).status_code == 400
    assert cliente.put("/config", json={"vercel_token": "x"}).status_code == 400
    assert not api.CONFIG.exists()
    assert cliente.put("/config", json={"modelo_mensagem": "chave: VERCEL_TOKEN {url}"}).status_code == 200


def test_leads_filtra_por_status(cliente, api):
    _semear(api, {"place_id": "p1", "nome": "A"}, {"place_id": "p2", "nome": "B"})
    api.store.set_status(api.DB, "p2", "aprovado")
    r = cliente.get("/leads", params={"status": "aprovado"})
    assert [lead["place_id"] for lead in r.json()] == ["p2"]
    assert r.json()[0]["tem_site"] is None  # sem site_url e sem verificação: não medido
    assert len(cliente.get("/leads").json()) == 2
    assert cliente.get("/leads", params={"status": "xyz"}).status_code == 400


def test_optout_persiste(cliente, api):
    _semear(api, {"place_id": "p1", "nome": "A"})
    assert cliente.post("/optout", json={"place_id": "p1"}).status_code == 200
    assert api.store.list_leads(api.DB, {"place_id": "p1"})[0]["optout"] == 1
    assert cliente.post("/optout", json={"place_id": " "}).status_code == 400


def test_rascunho_substitui_nome_e_url_sem_rede(cliente, api, monkeypatch):
    _semear(api, {"place_id": "p1", "nome": "Ana Doces"})
    cliente.put("/config", json={"assunto_padrao": "Oi {nome}", "modelo_mensagem": "Oi {nome}, veja {url}"})

    def sem_rede(*a, **k):
        raise AssertionError("rascunho não pode abrir conexão")

    monkeypatch.setattr(socket, "create_connection", sem_rede)
    monkeypatch.setattr(urllib.request, "urlopen", sem_rede)
    r = cliente.post("/rascunho", json={"place_id": "p1", "url": "https://ana.exemplo"})
    assert r.status_code == 200
    assert r.json() == {
        "email": {"assunto": "Oi Ana Doces", "corpo": "Oi Ana Doces, veja https://ana.exemplo"},
        "whatsapp": {"texto": "Oi Ana Doces, veja https://ana.exemplo"},
    }


def test_rascunho_modelo_com_url_sem_url_400(cliente, api):
    _semear(api, {"place_id": "p1", "nome": "Ana"})
    assert cliente.post("/rascunho", json={"place_id": "p1"}).status_code == 400


def test_rascunho_lead_inexistente_404(cliente):
    assert cliente.post("/rascunho", json={"place_id": "nao-existe"}).status_code == 404
