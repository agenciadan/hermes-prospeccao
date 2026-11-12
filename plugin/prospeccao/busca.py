import csv
import hashlib
import io
import json
import os
import time
import urllib.error
import urllib.request


class SourceError(Exception):
    pass


STATUS_FALHA = {"failed", "error", "cancelled", "canceled"}


def _http(metodo, url, corpo=None):  # único ponto de rede: os testes trocam esta função
    req = urllib.request.Request(url, data=corpo, method=metodo, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _req(metodo, url, corpo=None):
    status, resp = _http(metodo, url, corpo)
    if not 200 <= status < 300:
        raise SourceError(f"gosom HTTP {status} em {metodo} {url}")
    return resp


def _txt(valor):
    return (valor or "").strip() or None


def _numero(valor, tipo):
    # R26: não numérico ('N/A') ou ausente = não medido = None
    try:
        return tipo(valor)
    except (TypeError, ValueError):
        return None


def _lead(row, nicho, cidade):
    # R22: chave = place_id, senão data_id, senão sha1(nome|endereço|cidade)
    chave = (row.get("place_id") or "").strip() or (row.get("data_id") or "").strip()
    if not chave:
        base = f"{(row.get('title') or '').strip()}|{(row.get('address') or '').strip()}|{cidade}"
        chave = hashlib.sha1(base.encode()).hexdigest()
    return {
        "place_id": chave, "nome": _txt(row.get("title")), "nicho": nicho, "cidade": cidade,
        "nota": _numero(_txt(row.get("review_rating")), float),
        "avaliacoes": _numero(_txt(row.get("review_count")), int),
        "site_url": _txt(row.get("website")), "telefone": _txt(row.get("phone")),
        "email": _txt(row.get("emails")), "fonte": "gosom",
    }


def buscar(nicho, cidade, fonte, lat=None, lon=None, timeout=20 * 60, intervalo=5):
    # R23: lat/lon obrigatórios (sem geocodificação); R21: só gosom
    if lat is None or lon is None:
        raise ValueError("lat e lon são obrigatórios (sem geocodificação)")
    if fonte != "gosom":
        raise ValueError(f"fonte desconhecida: {fonte}")
    base = os.environ.get("GOSOM_URL", "https://maps.adxpro.com.br").rstrip("/")
    try:
        # gosom exige name, depth e max_time (422 "missing ..."); max_time = prazo, o job não roda além da espera
        termo = f"{nicho} em {cidade}"
        corpo = json.dumps({"name": termo, "keywords": [termo], "depth": 1, "lang": "pt",
                            "lat": str(lat), "lon": str(lon), "max_time": int(timeout)}).encode()
        job_id = json.loads(_req("POST", f"{base}/api/v1/jobs", corpo))["id"]
        prazo = time.monotonic() + timeout
        while True:
            status = json.loads(_req("GET", f"{base}/api/v1/jobs/{job_id}"))["Status"]
            if status == "ok":  # R27: ok no último ciclo é aceito, mesmo após o prazo
                break
            if status in STATUS_FALHA:  # R25: falha terminal não espera o prazo
                raise SourceError(f"gosom: job {job_id} terminou com status {status}")
            if time.monotonic() >= prazo:
                raise SourceError(f"gosom: job {job_id} não ficou ok em {timeout}s")
            time.sleep(intervalo)
        texto = _req("GET", f"{base}/api/v1/jobs/{job_id}/download").decode("utf-8-sig")
        leitor = csv.DictReader(io.StringIO(texto))
        if not leitor.fieldnames or "title" not in leitor.fieldnames:
            raise SourceError("gosom: CSV sem cabeçalho")
        return [_lead(row, nicho, cidade) for row in leitor]
    except SourceError:
        raise
    except Exception as e:  # rede, JSON inválido, chave ausente: nunca vira lista vazia
        raise SourceError(f"gosom: {e}") from e
