import hashlib
import importlib
import json
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "plugin"
CABECALHO = "input_id,link,title,address,website,phone,review_count,review_rating,data_id,place_id,emails\n"
POST_OK = (201, b'{"id": "j1"}')
JOB_OK = (200, b'{"ID": "j1", "Status": "ok"}')
JOB_PENDENTE = (200, b'{"ID": "j1", "Status": "pending"}')


@pytest.fixture
def busca(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_ROOT))  # restaurado ao fim do teste
    return importlib.import_module("prospeccao.busca")


def roteiro(monkeypatch, busca, respostas):
    """Transporte falso: devolve as respostas em ordem (ou levanta, se for exceção)."""
    chamadas, fila = [], list(respostas)

    def falso(metodo, url, corpo=None):
        chamadas.append((metodo, url, corpo))
        resp = fila.pop(0)
        if isinstance(resp, Exception):
            raise resp
        return resp

    monkeypatch.setattr(busca, "_http", falso)
    return chamadas


def linha(**campos):
    return ",".join(campos.get(c, "") for c in CABECALHO.strip().split(",")) + "\n"


def csv_resp(*linhas):
    return (200, (CABECALHO + "".join(linhas)).encode())


def test_mapeia_csv_para_lead(monkeypatch, busca):
    roteiro(monkeypatch, busca, [POST_OK, JOB_OK, csv_resp(
        "1,,Encanador X,Rua A 1,,27 99999-0000,12,4.5,0x1:0x2,p1,\n")])
    leads = busca.buscar("encanador", "Vitória", "gosom", lat="-20.3155", lon="-40.3128", intervalo=0)
    assert leads == [{"place_id": "p1", "nome": "Encanador X", "nicho": "encanador", "cidade": "Vitória",
                      "nota": 4.5, "avaliacoes": 12, "site_url": None, "telefone": "27 99999-0000",
                      "email": None, "fonte": "gosom"}]


def test_place_id_vazio_cai_para_data_id_com_strip(monkeypatch, busca):
    roteiro(monkeypatch, busca, [POST_OK, JOB_OK, csv_resp(linha(title="Loja", data_id="  0x1:0x2 ", place_id="  "))])
    leads = busca.buscar("x", "y", "gosom", lat="1", lon="2", intervalo=0)
    assert leads[0]["place_id"] == "0x1:0x2"


def test_sem_place_id_nem_data_id_usa_sha1_nome_endereco_cidade(monkeypatch, busca):
    roteiro(monkeypatch, busca, [POST_OK, JOB_OK, csv_resp(linha(title="Loja", address="Rua B"))])
    leads = busca.buscar("x", "Vitória", "gosom", lat="1", lon="2", intervalo=0)
    esperado = hashlib.sha1("Loja|Rua B|Vitória".encode()).hexdigest()
    assert leads[0]["place_id"] == esperado


def test_lat_lon_obrigatorios_sem_chamar_gosom(monkeypatch, busca):
    chamadas = roteiro(monkeypatch, busca, [])
    with pytest.raises(ValueError):
        busca.buscar("encanador", "Vitória", "gosom")
    assert chamadas == []


def test_post_envia_keyword_e_lat_lon_como_texto(monkeypatch, busca):
    chamadas = roteiro(monkeypatch, busca, [POST_OK, JOB_OK, csv_resp()])
    busca.buscar("encanador", "Vitória", "gosom", lat="-20.3155", lon="-40.3128", intervalo=0)
    metodo, url, corpo = chamadas[0]
    assert (metodo, url) == ("POST", "https://maps.adxpro.com.br/api/v1/jobs")
    assert json.loads(corpo) == {"name": "encanador em Vitória", "keywords": ["encanador em Vitória"], "depth": 1,
                                 "lang": "pt", "lat": "-20.3155", "lon": "-40.3128", "max_time": 1200}


def test_gosom_url_vem_do_ambiente(monkeypatch, busca):
    monkeypatch.setenv("GOSOM_URL", "http://localhost:8080/")
    chamadas = roteiro(monkeypatch, busca, [POST_OK, JOB_OK, csv_resp()])
    busca.buscar("x", "y", "gosom", lat="1", lon="2", intervalo=0)
    assert chamadas[0][1] == "http://localhost:8080/api/v1/jobs"


def test_espera_status_ok_antes_de_baixar(monkeypatch, busca):
    chamadas = roteiro(monkeypatch, busca, [POST_OK, JOB_PENDENTE, JOB_OK, csv_resp()])
    busca.buscar("x", "y", "gosom", lat="1", lon="2", intervalo=0)
    assert [m for m, _, _ in chamadas] == ["POST", "GET", "GET", "GET"]
    assert chamadas[3][1].endswith("/api/v1/jobs/j1/download")


def test_erro_de_rede_nao_vira_lista_vazia(monkeypatch, busca):
    roteiro(monkeypatch, busca, [ConnectionError("offline")])
    with pytest.raises(busca.SourceError):
        busca.buscar("encanador", "Vitória", "gosom", lat="1", lon="2", intervalo=0)


def test_http_nao_2xx_vira_source_error(monkeypatch, busca):
    roteiro(monkeypatch, busca, [(500, b"")])
    with pytest.raises(busca.SourceError):
        busca.buscar("encanador", "Vitória", "gosom", lat="1", lon="2", intervalo=0)


def test_status_nao_ok_ao_fim_do_prazo_vira_source_error(monkeypatch, busca):
    roteiro(monkeypatch, busca, [POST_OK, JOB_PENDENTE])
    with pytest.raises(busca.SourceError):
        busca.buscar("encanador", "Vitória", "gosom", lat="1", lon="2", timeout=0, intervalo=0)


def test_csv_sem_cabecalho_vira_source_error(monkeypatch, busca):
    roteiro(monkeypatch, busca, [POST_OK, JOB_OK, (200, b"")])
    with pytest.raises(busca.SourceError):
        busca.buscar("encanador", "Vitória", "gosom", lat="1", lon="2", intervalo=0)


def test_csv_so_cabecalho_retorna_lista_vazia(monkeypatch, busca):
    roteiro(monkeypatch, busca, [POST_OK, JOB_OK, csv_resp()])
    assert busca.buscar("encanador", "Vitória", "gosom", lat="1", lon="2", intervalo=0) == []


@pytest.mark.parametrize("status", ["failed", "error", "cancelled", "canceled"])
def test_status_terminal_de_falha_levanta_sem_esperar_prazo(monkeypatch, busca, status):
    chamadas = roteiro(monkeypatch, busca, [POST_OK, (200, json.dumps({"ID": "j1", "Status": status}).encode())])
    with pytest.raises(busca.SourceError):
        busca.buscar("x", "y", "gosom", lat="1", lon="2", timeout=1200, intervalo=0)
    assert [m for m, _, _ in chamadas] == ["POST", "GET"]


def test_nota_e_avaliacoes_nao_numericas_viram_none(monkeypatch, busca):
    roteiro(monkeypatch, busca, [POST_OK, JOB_OK, csv_resp(linha(title="Loja", data_id="0x1:0x2", review_rating="N/A", review_count="N/A"))])
    leads = busca.buscar("x", "y", "gosom", lat="1", lon="2", intervalo=0)
    assert (leads[0]["nota"], leads[0]["avaliacoes"]) == (None, None)


class Relogio:
    def __init__(self):
        self.t = 0.0

    def monotonic(self):
        return self.t

    def sleep(self, segundos):
        self.t += segundos


def test_status_ok_no_ciclo_apos_o_prazo_e_aceito(monkeypatch, busca):
    monkeypatch.setattr(busca, "time", Relogio())  # sleep avança o relógio além do prazo (5s)
    chamadas = roteiro(monkeypatch, busca, [POST_OK, JOB_PENDENTE, JOB_OK, csv_resp(linha(title="Loja", data_id="0x1:0x2"))])
    leads = busca.buscar("x", "y", "gosom", lat="1", lon="2", timeout=5, intervalo=10)
    assert [lead["nome"] for lead in leads] == ["Loja"]
    assert len(chamadas) == 4


def test_fonte_desconhecida_levanta_value_error(monkeypatch, busca):
    chamadas = roteiro(monkeypatch, busca, [])
    with pytest.raises(ValueError):
        busca.buscar("encanador", "Vitória", "scrapling", lat="1", lon="2")
    assert chamadas == []
