import sqlite3
from contextlib import closing
from datetime import datetime, timezone

SCHEMA = """CREATE TABLE IF NOT EXISTS leads (
    place_id TEXT PRIMARY KEY, nome TEXT, nicho TEXT, cidade TEXT,
    nota REAL NULL, avaliacoes INTEGER NULL, site_url TEXT NULL,
    telefone TEXT NULL, email TEXT NULL, fonte TEXT,
    status TEXT DEFAULT 'novo', optout INTEGER DEFAULT 0, updated_at TEXT)"""
COLUMNS = ("place_id", "nome", "nicho", "cidade", "nota", "avaliacoes", "site_url",
           "telefone", "email", "fonte", "status", "optout", "updated_at")
# status/optout só mudam por set_status/mark_optout: um upsert de busca não pode reabrir opt-out.
UPSERT_COLUMNS = tuple(c for c in COLUMNS if c not in ("status", "optout", "updated_at"))
VALID_STATUS = ("novo", "rascunho", "aprovado", "enviado", "respondeu", "erro")


def _now():
    return datetime.now(timezone.utc).isoformat()


def _vazio(place_id):  # só espaços conta como vazio
    return place_id is None or str(place_id).strip() == ""


def _connect(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def init_db(path):
    with closing(_connect(path)) as con, con:
        con.execute(SCHEMA)


def upsert_leads(path, leads):
    if any(_vazio(lead.get("place_id")) for lead in leads):  # valida o lote antes de gravar qualquer linha
        raise ValueError("place_id ausente, None ou vazio")
    now = _now()
    with closing(_connect(path)) as con, con:
        for lead in leads:
            # None e "" não entram no INSERT/UPDATE: não medido/vazio preserva o valor anterior
            row = {k: lead[k] for k in UPSERT_COLUMNS if k in lead and lead[k] not in (None, "")}
            row["place_id"] = lead["place_id"]
            row["updated_at"] = now
            sets = ", ".join(f"{k}=excluded.{k}" for k in row if k != "place_id")
            con.execute(
                f"INSERT INTO leads ({', '.join(row)}) VALUES ({', '.join('?' * len(row))}) "
                f"ON CONFLICT(place_id) DO UPDATE SET {sets}",
                list(row.values()))
    return len(leads)


def list_leads(path, filters):
    unknown = set(filters) - set(COLUMNS)
    if unknown:
        raise ValueError(f"filtro desconhecido: {sorted(unknown)}")
    conds = [f"{k} IS NULL" if v is None else f"{k}=?" for k, v in filters.items()]
    conds.append("NOT (nome IS NULL AND optout=1)")  # fantasma de opt-out (lead ainda não buscado): gravado, mas oculto
    params = [v for v in filters.values() if v is not None]
    sql = "SELECT * FROM leads WHERE " + " AND ".join(conds)
    with closing(_connect(path)) as con:
        return [dict(r) for r in con.execute(sql, params).fetchall()]


def set_status(path, place_id, status):
    if status not in VALID_STATUS:
        raise ValueError(f"status inválido: {status!r}")
    with closing(_connect(path)) as con, con:
        cur = con.execute("UPDATE leads SET status=?, updated_at=? WHERE place_id=?",
                          (status, _now(), place_id))
        if cur.rowcount == 0:  # sem isso, o erro some em silêncio
            raise ValueError(f"place_id inexistente: {place_id!r}")


def mark_optout(path, place_id):
    if _vazio(place_id):
        raise ValueError("place_id ausente, None ou vazio")
    with closing(_connect(path)) as con, con:
        # insere se o lead ainda não existe: o opt-out precisa sobreviver a uma busca posterior
        con.execute("INSERT INTO leads (place_id, optout, updated_at) VALUES (?, 1, ?) "
                    "ON CONFLICT(place_id) DO UPDATE SET optout=1, updated_at=excluded.updated_at",
                    (place_id, _now()))
