import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo; Eleventy e design.md ficam em node_modules locais (R29)
ELEVENTY = ROOT / "node_modules" / ".bin" / "eleventy"
DESIGN_MD_CLI = ROOT / "node_modules" / "@google" / "design.md" / "dist" / "index.js"
TEMPLATES = Path(__file__).resolve().parent / "templates"
# o exportador repete o nome das chaves do design.md sem escape; o template usa | safe, então só CSS puro passa
CSS_VARS_SEGURO = re.compile(r":root \{\n(  --[\w'\"-]+: [\w#.%-]+;\n)*\}\s*")  # \s*: console.log põe \n extra


def gerar_site(lead: dict, template: str, design_md: Path, refs: list[str], saida: Path) -> Path:
    design_md = Path(design_md)
    if not design_md.is_file():
        raise FileNotFoundError(f"DESIGN.md não encontrado: {design_md}")
    if not ELEVENTY.exists():
        raise RuntimeError(f"Eleventy não instalado em {ELEVENTY}: rode 'npm install' na raiz do repo")
    saida = Path(saida)

    tokens = subprocess.run(
        ["node", str(DESIGN_MD_CLI), "export", "--format", "css-vars", str(design_md)],
        check=True, capture_output=True, text=True).stdout
    if not CSS_VARS_SEGURO.fullmatch(tokens):
        raise ValueError("tokens do design.md fora do css-vars seguro: chaves com <, >, {, } ou espaços")

    with tempfile.TemporaryDirectory() as work:
        src = Path(work) / "src"
        shutil.copytree(TEMPLATES / template, src)
        (src / "_data").mkdir()
        (src / "_data" / "lead.json").write_text(json.dumps(lead, ensure_ascii=False))
        (src / "_data" / "design.json").write_text(json.dumps({"css": tokens}))
        subprocess.run([str(ELEVENTY), "--input", str(src), "--output", str(saida)],
                       check=True, cwd=work)

    (saida / "tokens.css").write_text(tokens)
    (saida / "refs").mkdir(exist_ok=True)
    for ref in refs:  # R30: só os arquivos listados pelo chamador; nunca diretório
        shutil.copy(ref, saida / "refs")
    return saida
