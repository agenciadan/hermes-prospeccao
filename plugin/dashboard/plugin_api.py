"""Prospecção dashboard API, montada pelo Hermes em /api/plugins/prospeccao/."""

import hashlib
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

PLUGIN = Path(__file__).resolve().parents[1]
# shortcut: o host carrega este arquivo com spec_from_file_location, sem plugin/ no sys.path; trocar por import de pacote se o host passar a incluí-lo
if str(PLUGIN) not in sys.path:
    sys.path.insert(0, str(PLUGIN))
from prospeccao import busca, config, filtro, publicar, site, store  # noqa: E402

DADOS = PLUGIN / "prospeccao"
DB = DADOS / "leads.db"
CONFIG = DADOS / "config.json"
SITES = DADOS / "sites"
DESIGN_MD = DADOS / "design.md"  # shortcut: caminho fixo; sem design.md a rota /site falha com 502, subir para configuração quando houver mais de um
TEMPLATE = "basico"

router = APIRouter()


class BuscaIn(BaseModel):
    nicho: str | None = None
    cidade: str | None = None
    lat: float | None = None
    lon: float | None = None
    confirmar: bool = False


class LeadIn(BaseModel):
    place_id: str | None = None


class ConfirmaIn(LeadIn):
    confirmar: bool = False


class PublicarIn(ConfirmaIn):
    provedor: str | None = None


class RascunhoIn(LeadIn):
    url: str | None = None


def _mascara(texto: str) -> str:
    # 502 não ecoa valor de variável sensível (token, chave, URL de serviço), mesmo que o módulo o cite
    for valor in config.segredos_do_ambiente():
        texto = texto.replace(valor, "***")
    return texto


def _db():
    store.init_db(DB)  # idempotente; cria o arquivo na primeira rota que usa o banco
    return DB


def _exige_confirmacao(confirmar: bool) -> None:
    if not confirmar:
        raise HTTPException(400, "ação externa: envie confirmar=true")


def _lead(place_id):
    achados = store.list_leads(_db(), {"place_id": place_id})
    if not achados:
        raise HTTPException(404, "lead não encontrado")
    return achados[0]


def _pasta(lead) -> Path:
    # place_id vem do usuário e do gosom: nunca vai cru para o caminho em disco
    return SITES / hashlib.sha256(lead["place_id"].encode()).hexdigest()[:16]


@router.get("/health")
async def health():
    return {"ok": True}


@router.get("/leads")
def rota_leads(status: str | None = None):
    if status is not None and status not in store.VALID_STATUS:
        raise HTTPException(400, "status inválido")
    filtros = {} if status is None else {"status": status}
    return [filtro.classificar(lead) for lead in store.list_leads(_db(), filtros)]


@router.post("/busca")
def rota_busca(body: BuscaIn):
    _exige_confirmacao(body.confirmar)
    if not all([(body.nicho or "").strip(), (body.cidade or "").strip()]) or body.lat is None or body.lon is None:
        raise HTTPException(400, "nicho, cidade, lat e lon são obrigatórios")
    if not (-90 <= body.lat <= 90 and -180 <= body.lon <= 180):
        raise HTTPException(400, "lat/lon fora do intervalo")
    try:
        leads = busca.buscar(body.nicho, body.cidade, "gosom", lat=body.lat, lon=body.lon)
    except busca.SourceError as e:
        raise HTTPException(502, _mascara(str(e)))
    return {"gravados": store.upsert_leads(_db(), leads)}


@router.post("/site")
def rota_site(body: ConfirmaIn):
    _exige_confirmacao(body.confirmar)
    lead = _lead(body.place_id)
    saida = _pasta(lead)
    try:
        site.gerar_site(lead, TEMPLATE, DESIGN_MD, [], saida)  # shortcut: sem refs; o chamador ainda não lista arquivos locais
    except (FileNotFoundError, RuntimeError, ValueError, subprocess.CalledProcessError) as e:
        raise HTTPException(502, _mascara(str(e)))
    return {"pasta": saida.name}


@router.post("/publicar")
def rota_publicar(body: PublicarIn):
    _exige_confirmacao(body.confirmar)
    if body.provedor not in config.PROVEDORES:
        raise HTTPException(400, "provedor inválido: use vercel ou cloudflare")
    pasta = _pasta(_lead(body.place_id))
    try:
        url = publicar.publicar(pasta, body.provedor, pasta.name)
    except publicar.PublishError as e:
        raise HTTPException(502, _mascara(str(e)))
    return {"url": url}


@router.post("/optout")
def rota_optout(body: LeadIn):  # sem confirmar: opt-out é proteção, não ação externa
    try:
        store.mark_optout(_db(), body.place_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"ok": True}


@router.get("/config")
def rota_ler_config():
    return config.ler(CONFIG)


@router.put("/config")
def rota_gravar_config(body: dict):
    try:
        return config.atualizar(CONFIG, body)
    except ValueError as e:
        raise HTTPException(400, str(e))


@router.post("/rascunho")
def rota_rascunho(body: RascunhoIn):
    lead = _lead(body.place_id)
    try:
        return config.rascunhar(config.ler(CONFIG), lead, body.url)
    except ValueError as e:
        raise HTTPException(400, str(e))
