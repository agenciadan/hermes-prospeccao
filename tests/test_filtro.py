import importlib
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "plugin"


@pytest.fixture
def filtro(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_ROOT))  # restaurado ao fim do teste
    return importlib.import_module("prospeccao.filtro")


def test_sem_site_e_none_quando_nao_sabe(filtro):
    assert filtro.classificar({"site_url": None, "verificado_site": False})["tem_site"] is None


def test_filtra_nota_minima_ignora_nulo(filtro):
    leads = [{"nota": 4.8}, {"nota": None}, {"nota": 3.0}]
    assert filtro.filtrar(leads, {"nota_min": 4.0}) == [{"nota": 4.8}]


def test_site_presente_e_true(filtro):
    assert filtro.classificar({"site_url": "https://exemplo.com.br"})["tem_site"] is True


def test_site_ausente_verificado_e_false(filtro):
    assert filtro.classificar({"site_url": None, "verificado_site": True})["tem_site"] is False


def test_verificado_site_so_conta_se_for_true_explicito(filtro):
    for valor in ("false", 1, "sim"):
        assert filtro.classificar({"site_url": None, "verificado_site": valor})["tem_site"] is None


def test_verificado_site_truthy_nao_passa_sem_site(filtro):
    leads = [{"site_url": None, "verificado_site": 1}, {"site_url": None, "verificado_site": "false"}]
    assert filtro.filtrar(leads, {"sem_site": True}) == []


def test_site_url_vazio_nao_existe_e_e_none(filtro):
    assert filtro.classificar({"site_url": ""})["tem_site"] is None


def test_site_url_so_espacos_nao_existe_e_e_none(filtro):
    assert filtro.classificar({"site_url": "  "})["tem_site"] is None


def test_site_url_vazio_ou_so_espacos_com_verificado_true_e_false(filtro):
    for site in ("", "  "):
        assert filtro.classificar({"site_url": site, "verificado_site": True})["tem_site"] is False


def test_sem_site_false_nao_filtra(filtro):
    leads = [{"site_url": "https://a.com.br"}, {"site_url": None}]
    assert filtro.filtrar(leads, {"sem_site": False}) == leads


def test_verificado_site_true_explicito_passa_sem_site(filtro):
    lead = {"site_url": None, "verificado_site": True}
    assert filtro.classificar(lead)["tem_site"] is False
    assert filtro.filtrar([lead], {"sem_site": True}) == [lead]


def test_classificar_nao_altera_o_lead_de_entrada(filtro):
    lead = {"site_url": None, "verificado_site": True}
    filtro.classificar(lead)
    assert "tem_site" not in lead


def test_nota_zero_e_valor_medido_e_passa_nota_min_zero(filtro):
    leads = [{"nota": 0.0}, {"nota": None}]
    assert filtro.filtrar(leads, {"nota_min": 0.0}) == [{"nota": 0.0}]


def test_nota_zero_abaixo_do_minimo_e_excluida(filtro):
    assert filtro.filtrar([{"nota": 0.0}], {"nota_min": 4.0}) == []


def test_avaliacoes_zero_e_valor_medido(filtro):
    leads = [{"avaliacoes": 0}, {"avaliacoes": None}]
    assert filtro.filtrar(leads, {"avaliacoes_min": 0}) == [{"avaliacoes": 0}]


def test_filtra_avaliacoes_minimas(filtro):
    leads = [{"avaliacoes": 120}, {"avaliacoes": 9}, {"avaliacoes": None}]
    assert filtro.filtrar(leads, {"avaliacoes_min": 10}) == [{"avaliacoes": 120}]


def test_sem_site_exclui_com_site_e_nao_sabido(filtro):
    leads = [
        {"site_url": "https://a.com.br"},
        {"site_url": None, "verificado_site": True},
        {"site_url": None},
    ]
    assert filtro.filtrar(leads, {"sem_site": True}) == [{"site_url": None, "verificado_site": True}]


def test_lista_vazia_devolve_lista_vazia(filtro):
    assert filtro.filtrar([], {"nota_min": 4.0}) == []
    assert filtro.filtrar([], {}) == []


def test_sem_criterios_nao_exclui_nenhum(filtro):
    leads = [{"nota": None}, {"nota": 2.0}]
    assert filtro.filtrar(leads, {}) == leads
