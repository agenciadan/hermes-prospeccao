import importlib
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "plugin"


@pytest.fixture
def store(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_ROOT))  # restaurado ao fim do teste
    return importlib.import_module("prospeccao.store")


@pytest.fixture
def db(tmp_path, store):
    path = str(tmp_path / "l.db")
    store.init_db(path)
    return path


def test_upsert_nao_duplica(store, db):
    lead = {"place_id": "p1", "nome": "A", "nota": None}
    store.upsert_leads(db, [lead])
    store.upsert_leads(db, [lead])
    assert len(store.list_leads(db, {})) == 1


def test_nao_medido_fica_null(store, db):
    store.upsert_leads(db, [{"place_id": "p1", "nome": "A", "nota": None}])
    assert store.list_leads(db, {})[0]["nota"] is None


def test_optout_marcado(store, db):
    store.upsert_leads(db, [{"place_id": "p1", "nome": "A"}])
    store.mark_optout(db, "p1")
    assert store.list_leads(db, {})[0]["optout"] == 1


def test_upsert_atualiza_so_campos_nao_nulos(store, db):
    store.upsert_leads(db, [{"place_id": "p1", "nome": "A", "nota": 4.5}])
    store.upsert_leads(db, [{"place_id": "p1", "nome": "B", "nota": None}])
    lead = store.list_leads(db, {})[0]
    assert lead["nome"] == "B"
    assert lead["nota"] == 4.5


def test_upsert_nao_reseta_status_nem_optout(store, db):
    store.upsert_leads(db, [{"place_id": "p1", "nome": "A"}])
    store.set_status(db, "p1", "aprovado")
    store.mark_optout(db, "p1")
    store.upsert_leads(db, [{"place_id": "p1", "nome": "A2"}])
    lead = store.list_leads(db, {})[0]
    assert lead["status"] == "aprovado"
    assert lead["optout"] == 1


def test_set_status_e_filtro(store, db):
    store.upsert_leads(db, [{"place_id": "p1", "nome": "A"}, {"place_id": "p2", "nome": "B"}])
    store.set_status(db, "p2", "enviado")
    assert [l["place_id"] for l in store.list_leads(db, {"status": "enviado"})] == ["p2"]


def test_filtro_com_coluna_desconhecida_falha(store, db):
    with pytest.raises(ValueError):
        store.list_leads(db, {"nome; DROP TABLE leads": "x"})


def test_optout_antes_do_lead_sobrevive_ao_upsert(store, db):
    store.mark_optout(db, "p1")  # lead ainda não existe: mark_optout insere a linha
    store.upsert_leads(db, [{"place_id": "p1", "nome": "A"}])
    assert store.list_leads(db, {})[0]["optout"] == 1


def test_place_id_ausente_ou_none_levanta_sem_gravar_lote(store, db):
    for bad in ({"nome": "X"}, {"place_id": None, "nome": "X"}):
        with pytest.raises(ValueError):
            store.upsert_leads(db, [{"place_id": "ok", "nome": "A"}, bad])
        assert store.list_leads(db, {}) == []


def test_mark_optout_com_place_id_none_levanta(store, db):
    with pytest.raises(ValueError):
        store.mark_optout(db, None)
    assert store.list_leads(db, {}) == []


def test_set_status_invalido_levanta(store, db):
    store.upsert_leads(db, [{"place_id": "p1", "nome": "A"}])
    with pytest.raises(ValueError):
        store.set_status(db, "p1", "qualquer")
    assert store.list_leads(db, {})[0]["status"] == "novo"


def test_set_status_id_inexistente_levanta(store, db):
    with pytest.raises(ValueError):
        store.set_status(db, "nao-existe", "enviado")


def test_upsert_com_telefone_vazio_nao_apaga_telefone(store, db):
    store.upsert_leads(db, [{"place_id": "p1", "nome": "A", "telefone": "11999"}])
    store.upsert_leads(db, [{"place_id": "p1", "nome": "A", "telefone": ""}])
    assert store.list_leads(db, {})[0]["telefone"] == "11999"


def test_filtro_nota_none_retorna_nota_null(store, db):
    store.upsert_leads(db, [{"place_id": "p1", "nome": "A", "nota": None},
                            {"place_id": "p2", "nome": "B", "nota": 4.0}])
    assert [l["place_id"] for l in store.list_leads(db, {"nota": None})] == ["p1"]
