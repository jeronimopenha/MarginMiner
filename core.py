"""Domínio e persistência. Valores decimais armazenados como texto exato no SQLite."""

from __future__ import annotations
import csv
import hashlib
import hmac
import io
import json
import os
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

D = Decimal

TYPES = (
    "APORTE",
    "RETIRADA",
    "COMPRA",
    "VENDA",
    "DIVIDENDO",
    "JCP",
    "TAXA",
    "DESDOBRAMENTO",
    "GRUPAMENTO",
    "BONIFICACAO",
    "AMORTIZACAO",
    "LIQUIDACAO",
)

FIELDS = [
    "id",
    "data",
    "ordem",
    "tipo",
    "ticker",
    "quantidade",
    "preco",
    "valor_bruto",
    "valor_liquido",
    "taxas",
    "fator",
    "observacao",
]

SCHEMA = """

CREATE TABLE IF NOT EXISTS schema_version(
    version INTEGER PRIMARY KEY
    );

INSERT OR IGNORE INTO schema_version VALUES(1);

CREATE TABLE IF NOT EXISTS users(
    id INTEGER PRIMARY KEY, 
    login TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    salt TEXT NOT NULL,
    password_hash TEXT NOT NULL
    );
 
CREATE TABLE IF NOT EXISTS assets(
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    ticker TEXT NOT NULL,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    UNIQUE(user_id,ticker)
    );
 
CREATE TABLE IF NOT EXISTS quotes(
    user_id INTEGER NOT NULL REFERENCES users(id), 
    ticker TEXT NOT NULL,
    date TEXT NOT NULL, 
    close TEXT NOT NULL,
    PRIMARY KEY(user_id,ticker,date),
    FOREIGN KEY(user_id,ticker) REFERENCES assets(user_id,ticker)
    );
 
CREATE TABLE IF NOT EXISTS movements(
    id TEXT NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id),
    data TEXT NOT NULL, 
    ordem INTEGER NOT NULL CHECK(ordem > 0), 
    tipo TEXT NOT NULL,
    ticker TEXT,
    quantidade TEXT NOT NULL, 
    preco TEXT NOT NULL,
    valor_bruto TEXT NOT NULL, 
    valor_liquido TEXT NOT NULL, 
    taxas TEXT NOT NULL, 
    fator TEXT NOT NULL,
    observacao TEXT NOT NULL,
    FOREIGN KEY(user_id,ticker) REFERENCES assets(user_id,ticker),
    UNIQUE(user_id,data,ordem), PRIMARY KEY(user_id,id)
    );
    
CREATE INDEX IF NOT EXISTS movements_date ON movements(user_id,data,ordem,id);
"""


class Store:
    def __init__(self, path=None):
        self.path = Path(
            path
            or os.environ.get(
                "CARTEIRA_DB", Path(__file__).parent / "data" / "carteira.sqlite3"
            )
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.executescript(SCHEMA)

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.path, timeout=15)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        try:
            with c:
                yield c
        finally:
            c.close()

    def rows(self, sql, params=()):
        with self.connect() as c:
            return [dict(x) for x in c.execute(sql, params)]

    def create_user(self, login, name, password):
        login, name = login.strip().lower(), name.strip()
        if not login or not name or len(password) < 10:
            raise ValueError("Informe login, nome e senha com ao menos 10 caracteres.")
        salt = secrets.token_hex(16)
        hashed = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1
        ).hex()
        with self.connect() as c:
            c.execute(
                "INSERT INTO users(login,name,salt,password_hash) VALUES(?,?,?,?)",
                (login, name, salt, hashed),
            )

    def authenticate(self, login, password):
        users = self.rows("SELECT * FROM users WHERE login=?", (login.strip().lower(),))
        if not users:
            return None
        u = users[0]
        hashed = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(u["salt"]), n=16384, r=8, p=1
        ).hex()
        return (
            {"id": u["id"], "name": u["name"]}
            if hmac.compare_digest(hashed, u["password_hash"])
            else None
        )

    def assets(self, uid):
        return self.rows(
            "SELECT ticker,name,category FROM assets WHERE user_id=? ORDER BY ticker",
            (uid,),
        )

    def asset(self, uid, ticker, name, category):
        ticker = ticker.strip().upper()
        if not ticker or not name.strip():
            raise ValueError("Ticker e nome são obrigatórios.")
        with self.connect() as c:
            c.execute(
                "INSERT INTO assets(user_id,ticker,name,category) VALUES(?,?,?,?)",
                (uid, ticker, name.strip(), category),
            )

    def movements(self, uid):
        sql_str = "SELECT " + ",".join(
            FIELDS
        ) + " FROM movements WHERE user_id=? ORDER BY data,ordem,id", (uid,)
        print(sql_str)
        return_ = self.rows(
            "SELECT "
            + ",".join(FIELDS)
            + " FROM movements WHERE user_id=? ORDER BY data,ordem,id",
            (uid,),
        )
        return return_

    def quotes(self, uid):
        return self.rows(
            "SELECT ticker,date,close FROM quotes WHERE user_id=? ORDER BY date,ticker",
            (uid,),
        )

    def save_movements(self, uid, raw):
        normalized = [normalize(x) for x in raw]
        with self.connect() as c:
            # Ids repetidos com conteúdo idêntico são ignorados; divergências abortam o lote.
            for row in normalized:
                prior = c.execute(
                    "SELECT * FROM movements WHERE id=? AND user_id=?", (row["id"], uid)
                ).fetchone()
                if prior:
                    if prior["user_id"] != uid or any(
                        str(prior[k] or "") != str(row[k] or "") for k in FIELDS
                    ):
                        raise ValueError(
                            "ID já existe com conteúdo diferente. Nada importado."
                        )
                    continue
                c.execute(
                    "INSERT INTO movements(user_id,"
                    + ",".join(FIELDS)
                    + ") VALUES("
                    + ",".join("?" for _ in range(len(FIELDS) + 1))
                    + ")",
                    [uid] + [row[k] for k in FIELDS],
                )
            records = [
                dict(x)
                for x in c.execute(
                    "SELECT * FROM movements WHERE user_id=? ORDER BY data,ordem,id",
                    (uid,),
                )
            ]
            replay(
                records
            )  # Rejeita saldo/posição negativos, inclusive em lançamentos retroativos.

    def delete(self, uid, mid):
        with self.connect() as c:
            c.execute("DELETE FROM movements WHERE id=? AND user_id=?", (mid, uid))
            replay(
                [
                    dict(x)
                    for x in c.execute(
                        "SELECT * FROM movements WHERE user_id=? ORDER BY data,ordem,id",
                        (uid,),
                    )
                ]
            )

    def save_quotes(self, uid, rows):
        values = []
        for r in rows:
            day = date.fromisoformat(str(r["date"])).isoformat()
            if day > date.today().isoformat():
                raise ValueError("Cotação futura não permitida.")
            close = number(r["close"])
            if close <= 0:
                raise ValueError("Cotação precisa ser positiva.")
            values.append((uid, str(r["ticker"]).strip().upper(), day, str(close)))
        with self.connect() as c:
            c.executemany(
                "INSERT INTO quotes VALUES(?,?,?,?) ON CONFLICT(user_id,ticker,date) DO UPDATE SET close=excluded.close",
                values,
            )

    def export(self, uid):
        return json.dumps(
            {
                "version": 1,
                "assets": self.assets(uid),
                "movements": self.movements(uid),
                "quotes": self.quotes(uid),
            },
            ensure_ascii=False,
            indent=2,
        ).encode()

    def restore(self, uid, content):
        data = json.loads(content)
        if data.get("version") != 1:
            raise ValueError("Versão de arquivo incompatível.")
        # Uma conexão externa mantém toda a importação atômica.
        assets = data["assets"]
        quotes = data["quotes"]
        movements = [normalize(r) for r in data["movements"]]
        replay(movements)
        with self.connect() as c:
            if (
                c.execute(
                    "SELECT 1 FROM movements WHERE user_id=? LIMIT 1", (uid,)
                ).fetchone()
                or c.execute(
                    "SELECT 1 FROM assets WHERE user_id=? LIMIT 1", (uid,)
                ).fetchone()
            ):
                raise ValueError(
                    "Restauração JSON requer usuário sem ativos e lançamentos. Use CSV para acrescentar lançamentos."
                )
            for a in assets:
                c.execute(
                    "INSERT INTO assets(user_id,ticker,name,category) VALUES(?,?,?,?)",
                    (uid, a["ticker"], a["name"], a["category"]),
                )
            for r in movements:
                c.execute(
                    "INSERT INTO movements(user_id,"
                    + ",".join(FIELDS)
                    + ") VALUES("
                    + ",".join("?" for _ in range(len(FIELDS) + 1))
                    + ")",
                    [uid] + [r[k] for k in FIELDS],
                )
            for r in quotes:
                close = number(r["close"])
                day = date.fromisoformat(r["date"]).isoformat()
                if close <= 0 or day > date.today().isoformat():
                    raise ValueError("Cotação inválida no arquivo.")
                c.execute(
                    "INSERT INTO quotes VALUES(?,?,?,?)",
                    (uid, r["ticker"], day, str(close)),
                )


def number(v):
    try:
        result = D(str(v).replace(",", "."))
        if not result.is_finite():
            raise ValueError("Número não finito.")
        return result
    except InvalidOperation:
        raise ValueError(f"Número inválido: {v}") from None


def normalize(raw):
    r = {k: raw.get(k, "") for k in FIELDS}
    r["id"] = str(r["id"] or uuid.uuid4())
    r["data"] = date.fromisoformat(str(r["data"])).isoformat()
    if r["data"] > date.today().isoformat():
        raise ValueError("Lançamentos futuros não permitidos.")
    r["ordem"] = int(r["ordem"] or 1)
    if r["ordem"] < 1:
        raise ValueError("Ordem precisa ser positiva.")
    r["tipo"] = str(r["tipo"]).upper()
    if r["tipo"] not in TYPES:
        raise ValueError("Tipo não implementado. Incorporações ainda não são aceitas.")
    r["ticker"] = str(r["ticker"] or "").strip().upper() or None
    r["observacao"] = str(r["observacao"] or "")
    for key in ("quantidade", "preco", "valor_bruto", "valor_liquido", "taxas", "fator"):
        r[key] = str(number(r[key] or ("1" if key == "fator" else "0")))
        if D(r[key]) < 0:
            raise ValueError("Use valores não negativos; o tipo determina o sinal.")
    t = r["tipo"]
    if t in ("APORTE", "RETIRADA", "TAXA"):
        if D(r["valor_bruto"]) <= 0 or D(r["valor_liquido"]) <= 0 or r["ticker"]:
            raise ValueError("Movimento de caixa exige valor positivo e nenhum ativo.")
    elif not r["ticker"]:
        raise ValueError("Selecione um ativo.")
    if t in ("COMPRA", "VENDA") and (D(r["quantidade"]) <= 0 or D(r["preco"]) <= 0):
        raise ValueError("Compra/venda exige quantidade e preço positivos.")
    if t in ("DIVIDENDO", "JCP", "AMORTIZACAO", "LIQUIDACAO") and D(r["valor"]) <= 0:
        raise ValueError("Informe o valor total líquido recebido.")
    if t == "BONIFICACAO" and D(r["quantidade"]) <= 0:
        raise ValueError("Informe a quantidade adicional recebida.")
    if t == "DESDOBRAMENTO" and D(r["fator"]) <= 1:
        raise ValueError("Desdobramento exige fator > 1. Ex.: 2 para 1:2.")
    if t == "GRUPAMENTO" and not 0 < D(r["fator"]) < 1:
        raise ValueError("Grupamento exige fator entre 0 e 1. Ex.: 0,1 para 10:1.")
    allowed = {
        "COMPRA": {"quantidade", "preco", "taxas"},
        "VENDA": {"quantidade", "preco", "taxas"},
        "BONIFICACAO": {"quantidade"},
        "DESDOBRAMENTO": {"fator"},
        "GRUPAMENTO": {"fator"},
    }.get(t, {"valor"})
    for k in ("quantidade", "preco", "valor_bruto", "valor_liquido", "taxas", "fator"):
        if k not in allowed and D(r[k]) != (1 if k == "fator" else 0):
            raise ValueError(f"O campo {k} não se aplica a {t}.")
    return r


def apply(r, cash, positions):
    t, a = r["tipo"], r["ticker"]
    q, p, v, fee, factor = (
        D(r[k]) for k in ("quantidade", "preco", "valor_bruto", "valor_liquido", "taxas", "fator")
    )
    held = positions.get(a, D(0))
    if t == "APORTE":
        cash += v
    elif t in ("RETIRADA", "TAXA"):
        cash -= v
    elif t == "COMPRA":
        cash -= q * p + fee
        positions[a] = held + q
    elif t == "VENDA":
        cash += q * p - fee
        positions[a] = held - q
    elif t in ("DIVIDENDO", "JCP", "AMORTIZACAO"):
        cash += v
    elif t in ("DESDOBRAMENTO", "GRUPAMENTO"):
        if held <= 0:
            raise ValueError("Evento de quantidade sem posição anterior.")
        positions[a] = held * factor
    elif t == "BONIFICACAO":
        if held <= 0:
            raise ValueError("Bonificação sem posição anterior.")
        positions[a] = held + q
    elif t == "LIQUIDACAO":
        if held <= 0:
            raise ValueError("Liquidação sem posição anterior.")
        cash += v
        positions[a] = D(0)
    if cash < 0 or any(qty < 0 for qty in positions.values()):
        raise ValueError(
            f"{r['data']} / {t}: saldo ou quantidade ficaria negativo. Confira aportes e ordem dos eventos."
        )
    return cash


def replay(rows):
    cash, pos = D(0), {}
    for r in sorted(rows, key=lambda x: (x["data"], int(x["ordem"]), x["id"])):
        cash = apply(r, cash, pos)
    return cash, pos


def history(rows, quotes, end=None):
    """Cotização diária: fluxos externos no início do dia, marcação no fechamento.

    Fecha o dia anterior para precificar aportes/retiradas; a convenção não é
    TWR intradiário exato. Ausência de cotação anterior bloqueia o cálculo.
    """
    if not rows:
        return []
    byday, qday = {}, {}
    for r in rows:
        byday.setdefault(r["data"], []).append(r)
    for q in quotes:
        qday.setdefault(q["date"], {})[q["ticker"]] = D(q["close"])
    start = date.fromisoformat(min(byday))
    end = end or date.today()
    cash, units, unit = D(0), D(0), D(1)
    pos, prices, lastquote = {}, {}, {}
    output = []
    day = start
    # Inclusive para cotações anteriores à primeira movimentação.
    for d in sorted(qday):
        if d < start.isoformat():
            prices.update(qday[d])
            lastquote.update({a: d for a in qday[d]})
    while day <= end:
        ds = day.isoformat()
        daily = sorted(byday.get(ds, []), key=lambda x: (int(x["ordem"]), x["id"]))
        flow = sum(
            (
                D(r["valor"]) * (1 if r["tipo"] == "APORTE" else -1)
                for r in daily
                if r["tipo"] in ("APORTE", "RETIRADA")
            ),
            D(0),
        )
        if unit <= 0:
            raise ValueError("Cota não positiva; cálculo precisa de revisão.")
        units += flow / unit
        for r in daily:
            cash = apply(r, cash, pos)
        # Ajusta o último preço conhecido se o evento ocorrer em dia sem cotação.
        for r in daily:
            if r["tipo"] in ("DESDOBRAMENTO", "GRUPAMENTO") and r["ticker"] in prices:
                prices[r["ticker"]] /= D(r["fator"])
        prices.update(qday.get(ds, {}))
        lastquote.update({a: ds for a in qday.get(ds, {})})
        missing = [a for a, q in pos.items() if q and a not in prices]
        if missing:
            raise ValueError(
                f"Falta cotação em {ds} ou anterior: {', '.join(missing)}."
            )
        nav = cash + sum((q * prices.get(a, D(0)) for a, q in pos.items()), D(0))
        if units < 0 or (units == 0 and nav != 0):
            raise ValueError(
                "Fluxo incompatível com cotização pela convenção diária. Confira datas e saldo."
            )
        if units:
            unit = nav / units
        output.append(
            {
                "data": ds,
                "patrimonio": float(nav),
                "saldo": float(cash),
                "cotas": float(units),
                "valor_cota": float(unit),
                "retorno_acumulado_pct": float((unit - 1) * 100),
                "cotacao_antiga": ", ".join(
                    a
                    for a, q in pos.items()
                    if q and (day - date.fromisoformat(lastquote[a])).days > 7
                ),
            }
        )
        day += timedelta(days=1)
    return output


def csv_bytes(rows, fields=FIELDS):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, delimiter=";")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


def parse_csv(content):
    return list(csv.DictReader(io.StringIO(content.decode("utf-8-sig")), delimiter=";"))
