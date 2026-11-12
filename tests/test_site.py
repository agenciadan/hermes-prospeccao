import importlib
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "plugin"


@pytest.fixture
def site(monkeypatch):
    monkeypatch.syspath_prepend(str(PLUGIN_ROOT))  # restaurado ao fim do teste
    return importlib.import_module("prospeccao.site")


@pytest.fixture
def design(tmp_path):
    path = tmp_path / "design.md"
    path.write_text("# cor: #0a0")
    return path


def test_gera_index_com_nome_do_lead(site, design, tmp_path):
    out = site.gerar_site({"nome": "Encanador X"}, "basico", design, [], tmp_path / "out")
    assert "Encanador X" in (out / "index.html").read_text()


def test_escapa_nome_do_lead_no_html(site, design, tmp_path):
    out = site.gerar_site({"nome": "A & <b>x</b>"}, "basico", design, [], tmp_path / "out")
    html = (out / "index.html").read_text()
    assert "A &amp; &lt;b&gt;x&lt;/b&gt;" in html
    assert "<b>x</b>" not in html


def test_design_md_ausente_falha(site, tmp_path):
    with pytest.raises(FileNotFoundError):
        site.gerar_site({"nome": "X"}, "basico", tmp_path / "nao.md", [], tmp_path / "out")


def test_copia_tokens_e_refs(site, design, tmp_path):
    ref = tmp_path / "ref.txt"
    ref.write_text("referencia")
    out = site.gerar_site({"nome": "X"}, "basico", design, [str(ref)], tmp_path / "out")
    assert (out / "tokens.css").exists()
    assert (out / "refs" / "ref.txt").read_text() == "referencia"


def test_eleventy_ausente_falha_com_mensagem_clara(site, design, tmp_path, monkeypatch):
    monkeypatch.setattr(site, "ELEVENTY", tmp_path / "nao-instalado")
    with pytest.raises(RuntimeError, match="npm install"):
        site.gerar_site({"nome": "X"}, "basico", design, [], tmp_path / "out")


def test_tokens_do_design_md_chegam_ao_index(site, tmp_path):
    design = tmp_path / "design.md"
    design.write_text('---\ncolors:\n  primary: "#1A7F37"\n---\n# Teste\n')
    out = site.gerar_site({"nome": "X"}, "basico", design, [], tmp_path / "out")
    html = (out / "index.html").read_text()
    assert "--color-primary: #1a7f37" in html
    assert "var(--color-primary)" in html
    assert "var(--font-body" in html


def test_css_malicioso_do_design_md_nao_sai_do_style(site, tmp_path):
    # o parser descarta valor de cor inválido; o exportador só reproduz o NOME da chave, sem escape
    design = tmp_path / "design.md"
    design.write_text('---\ncolors:\n  "a</style><script>alert(1)</script>": "#0a0"\n---\n')
    with pytest.raises(ValueError, match="css-vars seguro") as erro:
        site.gerar_site({"nome": "X"}, "basico", design, [], tmp_path / "out")
    assert "chave" in str(erro.value)
    assert all(c in str(erro.value) for c in "&/\\;()<>'\"")
    assert not (tmp_path / "out" / "index.html").exists()


@pytest.mark.parametrize("chave", ['"x\'y"', '"x\\"y"'])
def test_aspas_na_chave_do_design_md_falham(site, tmp_path, chave):
    design = tmp_path / "design.md"
    design.write_text(f"---\ncolors:\n  {chave}: \"#0a0\"\n---\n")
    with pytest.raises(ValueError, match="chave"):
        site.gerar_site({"nome": "X"}, "basico", design, [], tmp_path / "out")
    assert not (tmp_path / "out" / "index.html").exists()


def test_valor_fora_do_css_seguro_aponta_valor(site):
    with pytest.raises(ValueError, match="valor") as erro:
        site.valida_tokens(":root {\n  --color-x: a;b;\n}\n")
    assert "chave" not in str(erro.value)


def test_escapa_script_no_nome_do_lead(site, design, tmp_path):
    out = site.gerar_site({"nome": "<script>alert(1)</script>"}, "basico", design, [], tmp_path / "out")
    html = (out / "index.html").read_text()
    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;" in html


def test_refs_so_copia_arquivos_listados(site, design, tmp_path):
    pasta = tmp_path / "pasta"
    pasta.mkdir()
    (pasta / "a.txt").write_text("a")
    (pasta / "b.txt").write_text("b")
    out = site.gerar_site({"nome": "X"}, "basico", design, [str(pasta / "a.txt")], tmp_path / "out")
    assert sorted(p.name for p in (out / "refs").iterdir()) == ["a.txt"]
