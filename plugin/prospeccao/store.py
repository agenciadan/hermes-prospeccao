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


def _now():
    return datetime.now(timezone.utc).isoformat()


def _connect(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def init_db(path):
    with closing(_connect(path)) as con, con:
        con.execute(SCHEMA)


def upsert_leads(path, leads):
    now = _now()
    with closing(_connect(path)) as con, con:
        for lead in leads:
            # campos None não entram no INSERT/UPDATE: não medido preserva o valor anterior
            row = {k: lead[k] for k in UPSERT_COLUMNS if k in lead and lead[k] is not None}
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
    where = " AND ".join(f"{k}=?" for k in filters)
    sql = "SELECT * FROM leads" + (f" WHERE {where}" if where else "")
    with closing(_connect(path)) as con:
        return [dict(r) for r in con.execute(sql, list(filters.values())).fetchall()]


def set_status(path, place_id, status):
    with closing(_connect(path)) as con, con:
        con.execute("UPDATE leads SET status=?, updated_at=? WHERE place_id=?",
                    (status, _now(), place_id))


def mark_optout(path, place_id):
    with closing(_connect(path)) as con, con:
        con.execute("UPDATE leads SET optout=1, updated_at=? WHERE place_id=?",
                    (_now(), place_id))
