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
# barreira contra XSS: o exportador repete chaves e valores do design.md sem escape; o template usa | safe
CSS_VARS_SEGURO = re.compile(r":root \{\n(  --[\w-]+: [\w#.%-]+;\n)*\}\s*")  # \s*: console.log põe \n extra
PROIBIDOS = "& / \\ ; ( ) < > ' \""


def valida_tokens(tokens: str) -> None:
    if CSS_VARS_SEGURO.fullmatch(tokens):
        return
    # a mensagem diz se saiu a chave ou o valor (a chave é o que vem antes de ': ' em cada linha)
    chaves = re.findall(r"^  --(.*?): ", tokens, re.M)
    campo = "chave" if any(not re.fullmatch(r"[\w-]+", c) for c in chaves) else "valor"
    raise ValueError(f"{campo} dos tokens do design.md fora do css-vars seguro (proibido: {PROIBIDOS})")


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
    valida_tokens(tokens)

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
