"""Configuração de comunicação e publicação: JSON no diretório do plugin, sem segredos."""

import json
import os
import re
import tempfile
from pathlib import Path

CANAIS = ("whatsapp", "email")
PROVEDORES = ("vercel", "cloudflare")
PADROES = {
    "canal_padrao": "email",
    "remetente_email": "",
    "assunto_padrao": "",
    "modelo_mensagem": "Olá {nome}, criei uma página para o seu negócio: {url}",
    "publicar_provedor_padrao": "vercel",
}
SENSIVEIS = ("TOKEN", "KEY", "SECRET", "PASSWORD", "ACCOUNT", "URL")


def segredos_do_ambiente() -> list[str]:
    # shortcut: valores curtos (<8) não são comparados, para não bloquear texto comum; subir se virar falso negativo
    return [v for nome, v in os.environ.items() if len(v) >= 8 and any(s in nome for s in SENSIVEIS)]


def validar(parcial: dict) -> None:
    desconhecidas = set(parcial) - set(PADROES)
    if desconhecidas:  # tokens entram aqui por engano: campo fora da lista não é guardado
        raise ValueError(f"campo desconhecido (segredos não ficam na configuração): {sorted(desconhecidas)}")
    for chave, valor in parcial.items():
        if not isinstance(valor, str):
            raise ValueError(f"{chave} deve ser texto")
        if any(segredo in valor for segredo in segredos_do_ambiente()):
            raise ValueError(f"{chave} contém valor de variável de ambiente sensível: guarde só o nome")
    if "canal_padrao" in parcial and parcial["canal_padrao"] not in CANAIS:
        raise ValueError("canal_padrao inválido: use whatsapp ou email")
    if "publicar_provedor_padrao" in parcial and parcial["publicar_provedor_padrao"] not in PROVEDORES:
        raise ValueError("publicar_provedor_padrao inválido: use vercel ou cloudflare")
    if parcial.get("remetente_email") and not re.fullmatch(r"[^@\s]+@[^@\s]+", parcial["remetente_email"]):
        raise ValueError("remetente_email inválido")


def ler(path: Path) -> dict:
    guardado = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return {**PADROES, **{k: v for k, v in guardado.items() if k in PADROES}}


def atualizar(path: Path, parcial: dict) -> dict:
    validar(parcial)
    nova = {**ler(path), **parcial}  # JSON corrompido levanta antes de gravar: nada é sobrescrito
    _gravar(path, nova)
    return nova


def _gravar(path: Path, dados: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".config-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def _preencher(texto: str, lead: dict, url: str | None) -> str:
    return texto.replace("{nome}", lead.get("nome") or "").replace("{url}", url or "")


def rascunhar(cfg: dict, lead: dict, url: str | None) -> dict:
    # não envia nada: só monta o texto para o usuário aprovar
    if "{url}" in cfg["modelo_mensagem"] and not url:
        raise ValueError("url da landing ausente: o modelo usa {url}")
    corpo = _preencher(cfg["modelo_mensagem"], lead, url)
    return {"email": {"assunto": _preencher(cfg["assunto_padrao"], lead, url), "corpo": corpo},
            "whatsapp": {"texto": corpo}}
