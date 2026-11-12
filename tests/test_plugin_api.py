import importlib.util
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent
API_FILE = REPO_ROOT / "plugin" / "dashboard" / "plugin_api.py"
HOST_ROOT = Path.home() / ".hermes" / "hermes-agent"


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


def test_host_descobre_plugin(tmp_path):
    if not HOST_ROOT.is_dir():
        pytest.skip(f"host Hermes ausente: {HOST_ROOT}")
    sys.path.insert(0, str(HOST_ROOT))
    from hermes_cli.web_server_dashboard import _discover_dashboard_plugins

    plugins_dir = tmp_path / "plugins"
    plugins_dir.mkdir()
    (plugins_dir / "prospeccao").symlink_to(REPO_ROOT / "plugin", target_is_directory=True)

    found = _discover_dashboard_plugins(search_dirs=[(plugins_dir, "test")])
    entry = next((p for p in found if p.get("name") == "prospeccao"), None)
    assert entry is not None, f"prospeccao não descoberto pelo host: {found}"
    assert entry["has_api"] is True
