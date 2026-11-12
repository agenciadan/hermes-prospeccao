import importlib.util
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

API_FILE = Path(__file__).resolve().parent.parent / "plugin" / "dashboard" / "plugin_api.py"


def _load_router():
    spec = importlib.util.spec_from_file_location("prospeccao_plugin_api", API_FILE)
    assert spec and spec.loader, f"plugin_api não encontrado: {API_FILE}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.router


def test_health_returns_ok():
    app = FastAPI()
    app.include_router(_load_router())
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"ok": True}
