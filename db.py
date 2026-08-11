"""SQLite bilan ishlash qatlami. Bitta foydalanuvchi uchun mo'ljallangan, lekin
user_id bo'yicha ajratilgan — kerak bo'lsa bir nechta odam ishlatishi mumkin."""

from __future__ import annotations

import math
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from typing import Iterable

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    kind         TEXT    NOT NULL,
    amount       REAL    NOT NULL,
    category     TEXT    NOT NULL,
    note         TEXT    NOT NULL DEFAULT '',
    person       TEXT,
    occurred_on  TEXT    NOT NULL,
    raw_text     TEXT    NOT NULL DEFAULT '',
    settled      INTEGER NOT NULL DEFAULT 0,
    receipt_id   TEXT,
    currency     TEXT    NOT NULL DEFAULT 'som',
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_tx_user_date ON transactions(user_id, occurred_on);
CREATE INDEX IF NOT EXISTS idx_tx_user_kind ON transactions(user_id, kind);

-- Foydalanuvchilar: kirish huquqi, bepul sinov va obuna muddati.
CREATE TABLE IF NOT EXISTS users (
    user_id          INTEGER PRIMARY KEY,
    first_name       TEXT    NOT NULL DEFAULT '',
    username         TEXT,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    trial_ends_at    TEXT,
    subscribed_until TEXT,
    blocked          INTEGER NOT NULL DEFAULT 0,
    last_seen_at     TEXT
);

-- Har bir AI chaqiruvining haqiqiy token sarfi va narxi.
-- Kunlik limit ham shu jadvaldagi qatorlar soni bo'yicha hisoblanadi.
CREATE TABLE IF NOT EXISTS usage_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER NOT NULL,
    day           TEXT    NOT NULL,
    operation     TEXT    NOT NULL,
    model         TEXT    NOT NULL DEFAULT '',
    input_tokens  INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read    INTEGER NOT NULL DEFAULT 0,
    cache_write   INTEGER NOT NULL DEFAULT 0,
    cost_usd      REAL    NOT NULL DEFAULT 0,
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_usage_user_day ON usage_log(user_id, day);
CREATE INDEX IF NOT EXISTS idx_usage_day ON usage_log(day);

-- Obuna so'rovlari. Bot bu yerga yozadi, admin web panel o'qib hal qiladi.
-- Sxema admin panel bilan bir xil bo'lishi shart (hisobchim-admin/store.py).
CREATE TABLE IF NOT EXISTS subscription_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    plan_code   TEXT    NOT NULL,
    price       INTEGER NOT NULL DEFAULT 0,
    status      TEXT    NOT NULL DEFAULT 'kutilmoqda',
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    decided_at  TEXT,
    decided_by  TEXT    NOT NULL DEFAULT '',
    note        TEXT    NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_req_status ON subscription_requests(status, created_at DESC);

-- Valyuta kurslari. Har kun uchun bir marta saqlanadi, shunda o'tgan
-- oylardagi hisobot kurs o'zgarganda ham o'zgarmaydi.
CREATE TABLE IF NOT EXISTS rates (
    day      TEXT NOT NULL,
    currency TEXT NOT NULL,
    rate     REAL NOT NULL,
    source   TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (day, currency)
);

-- Kategoriya bo'yicha oylik byudjet. 80% va 100% da bir martadan
-- ogohlantiriladi; `notified` shu oyni «YYYY-MM:daraja» ko'rinishida saqlaydi.
CREATE TABLE IF NOT EXISTS budgets (
    user_id   INTEGER NOT NULL,
    category  TEXT    NOT NULL,
    amount    REAL    NOT NULL,
    currency  TEXT    NOT NULL DEFAULT 'som',
    notified  TEXT    NOT NULL DEFAULT '',
    PRIMARY KEY (user_id, category, currency)
);
"""

# Eski bazalarga keyin qo'shilgan ustunlar. CREATE TABLE IF NOT EXISTS mavjud
# jadvalni o'zgartirmaydi, shuning uchun qo'lda tekshiramiz.
MIGRATIONS = [
    ("receipt_id", "ALTER TABLE transactions ADD COLUMN receipt_id TEXT"),
    ("currency", "ALTER TABLE transactions ADD COLUMN currency TEXT NOT NULL DEFAULT 'som'"),
]

# Boshqa jadvallarga keyin qo'shilgan ustunlar: (jadval, ustun, SQL)
TABLE_MIGRATIONS = [
    ("subscription_requests", "proof_file_id",
     "ALTER TABLE subscription_requests ADD COLUMN proof_file_id TEXT"),
    ("subscription_requests", "proof_at",
     "ALTER TABLE subscription_requests ADD COLUMN proof_at TEXT"),
    # Chek rasm ham, PDF ham bo'lishi mumkin — admin panel qaysi
    # ko'rinishda chizishni shu ustundan biladi.
    ("subscription_requests", "proof_kind",
     "ALTER TABLE subscription_requests ADD COLUMN proof_kind TEXT NOT NULL DEFAULT 'rasm'"),
    ("users", "referred_by", "ALTER TABLE users ADD COLUMN referred_by INTEGER"),
    ("users", "bonus_days",
     "ALTER TABLE users ADD COLUMN bonus_days INTEGER NOT NULL DEFAULT 0"),
    ("users", "reminder_hour", "ALTER TABLE users ADD COLUMN reminder_hour INTEGER"),
    ("users", "warned_stage",
     "ALTER TABLE users ADD COLUMN warned_stage INTEGER NOT NULL DEFAULT 0"),
    ("users", "lang", "ALTER TABLE users ADD COLUMN lang TEXT NOT NULL DEFAULT 'uz'"),
    # Yozuv kiritilgan paytdagi kurs va asosiy valyutadagi qiymati.
    # Shu ikkisi bo'lgani uchun so'm va dollar bitta jamlanmada qo'shiladi.
    ("transactions", "rate", "ALTER TABLE transactions ADD COLUMN rate REAL NOT NULL DEFAULT 1"),
    ("transactions", "amount_base", "ALTER TABLE transactions ADD COLUMN amount_base REAL"),
]


@contextmanager
def get_conn():
    # timeout: boshqa jarayon (bot yoki webapp) yozayotgan bo'lsa kutadi,
    # darhol "database is locked" bermaydi.
    conn = sqlite3.connect(config.DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # WAL: bot.py va webapp.py bir vaqtda o'qishi/yozishi mumkin — o'qish
    # yozishni bloklamaydi. Bir marta o'rnatiladi, keyingi ulanishlarga ham tegishli.
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        existing = {r["name"] for r in conn.execute("PRAGMA table_info(transactions)")}
        for column, sql in MIGRATIONS:
            if column not in existing:
                conn.execute(sql)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tx_receipt ON transactions(user_id, receipt_id)"
        )
        for table, column, sql in TABLE_MIGRATIONS:
            cols = {r["name"] for r in conn.execute(f"PRAGMA table_info({table})")}
            if cols and column not in cols:
                conn.execute(sql)
        # Eski yozuvlarda amount_base bo'sh: so'mlilarini darhol to'ldiramiz,
        # valyutalilarini backfill_base() tarmoq orqali kurs olib to'ldiradi.
        conn.execute(
            "UPDATE transactions SET amount_base = amount, rate = 1 "
            "WHERE amount_base IS NULL AND currency = 'som'")


def backfill_base(default_rate: float | None = None) -> int:
    """amount_base bo'sh qolgan valyutali yozuvlarni to'ldiradi.

    Har bir yozuv uchun O'SHA KUNDAGI kurs olinadi — bugungisi emas.
    """
    import rates as rates_module

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, amount, currency, occurred_on FROM transactions "
            "WHERE amount_base IS NULL").fetchall()
        filled = 0
        for r in rows:
            try:
                day = date.fromisoformat(r["occurred_on"])
            except (TypeError, ValueError):
                day = date.today()
            try:
                rate = rates_module.get(r["currency"], day)
            except Exception:
                rate = default_rate or config.USD_RATE_FALLBACK
            conn.execute(
                "UPDATE transactions SET rate = ?, amount_base = ? WHERE id = ?",
                (rate, round(float(r["amount"]) * rate, 2), r["id"]))
            filled += 1
    return filled


# --------------------------------------------------------------------------- #
# Kurslar
# --------------------------------------------------------------------------- #

def get_rate(currency: str, day: date) -> float | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT rate FROM rates WHERE day = ? AND currency = ?",
            (day.isoformat(), currency.lower())).fetchone()
        return float(row["rate"]) if row else None


def set_rate(currency: str, day: date, rate: float, source: str = "") -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO rates (day, currency, rate, source) VALUES (?,?,?,?) "
            "ON CONFLICT(day, currency) DO UPDATE SET rate = excluded.rate, "
            "source = excluded.source",
            (day.isoformat(), currency.lower(), float(rate), source))


def rate_source(currency: str, day: date) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT source FROM rates WHERE day = ? AND currency = ?",
            (day.isoformat(), currency.lower())).fetchone()
        return row["source"] if row else None


def latest_rate(currency: str) -> float | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT rate FROM rates WHERE currency = ? ORDER BY day DESC LIMIT 1",
            (currency.lower(),)).fetchone()
        return float(row["rate"]) if row else None


# --------------------------------------------------------------------------- #
# Yozish
# --------------------------------------------------------------------------- #

def _base_of(amount: float, currency: str, occurred_on: str) -> tuple[float, float]:
    """(kurs, asosiy valyutadagi summa). So'm uchun kurs 1.

    Kurs olishda tarmoq xatosi bo'lsa ham yozuv yo'qolmasligi kerak —
    shuning uchun har qanday xatolikda zaxira qiymatga tushamiz.
    """
    if (currency or "som").lower() == "som":
        return 1.0, round(float(amount), 2)
    try:
        import rates as rates_module
        day = date.fromisoformat(occurred_on)
        rate = rates_module.get(currency, day)
    except Exception:                       # tarmoq, format yoki boshqa xato
        rate = float(config.USD_RATE_FALLBACK)
    return rate, round(float(amount) * rate, 2)


def add_transaction(
    user_id: int,
    kind: str,
    amount: float,
    category: str,
    note: str = "",
    person: str | None = None,
    occurred_on: str | None = None,
    raw_text: str = "",
    receipt_id: str | None = None,
    currency: str = "som",
) -> int:
    occurred_on = occurred_on or date.today().isoformat()
    rate, amount_base = _base_of(amount, currency, occurred_on)
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO transactions
               (user_id, kind, amount, category, note, person, occurred_on,
                raw_text, receipt_id, currency, rate, amount_base)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, kind, float(amount), category, note, person,
             occurred_on, raw_text, receipt_id, currency, rate, amount_base),
        )
        return int(cur.lastrowid)


def add_many(rows: list[dict]) -> list[int]:
    """Bir nechta yozuvni bitta tranzaksiyada saqlaydi (chek uchun)."""
    ids: list[int] = []
    # Kurs bitta chek uchun bir marta hisoblanadi — hamma qator bir kunda
    # va bir valyutada bo'ladi.
    prepared = [
        (r, *_base_of(r["amount"], r.get("currency", "som"), r["occurred_on"]))
        for r in rows
    ]
    with get_conn() as conn:
        for r, rate, amount_base in prepared:
            cur = conn.execute(
                """INSERT INTO transactions
                   (user_id, kind, amount, category, note, person, occurred_on,
                    raw_text, receipt_id, currency, rate, amount_base)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (r["user_id"], r["kind"], float(r["amount"]), r["category"],
                 r.get("note", ""), r.get("person"), r["occurred_on"],
                 r.get("raw_text", ""), r.get("receipt_id"),
                 r.get("currency", "som"), rate, amount_base),
            )
            ids.append(int(cur.lastrowid))
    return ids


def delete_transaction(user_id: int, tx_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM transactions WHERE id = ? AND user_id = ?", (tx_id, user_id)
        )
        return cur.rowcount > 0


def update_category(user_id: int, tx_id: int, category: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE transactions SET category = ? WHERE id = ? AND user_id = ?",
            (category, tx_id, user_id),
        )
        return cur.rowcount > 0


def update_kind(user_id: int, tx_id: int, kind: str, category: str) -> bool:
    """Yozuv turini (kirim/chiqim) almashtiradi va kategoriyani shu turga mos
    boshlang'ich qiymatga qaytaradi — eski kategoriya yangi turga to'g'ri kelmasligi mumkin."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE transactions SET kind = ?, category = ? WHERE id = ? AND user_id = ?",
            (kind, category, tx_id, user_id),
        )
        return cur.rowcount > 0


def settle_debt(user_id: int, tx_id: int) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE transactions SET settled = 1 WHERE id = ? AND user_id = ? AND kind IN (?, ?)",
            (tx_id, user_id, config.KIND_QARZ_BERDIM, config.KIND_QARZ_OLDIM),
        )
        return cur.rowcount > 0


# --------------------------------------------------------------------------- #
# O'qish
# --------------------------------------------------------------------------- #

def get_transaction(user_id: int, tx_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM transactions WHERE id = ? AND user_id = ?", (tx_id, user_id)
        )
        return cur.fetchone()


def list_range(
    user_id: int,
    start: date,
    end: date,
    kinds: Iterable[str] | None = None,
) -> list[sqlite3.Row]:
    kinds = list(kinds) if kinds else config.KINDS
    placeholders = ",".join("?" * len(kinds))
    with get_conn() as conn:
        cur = conn.execute(
            f"""SELECT * FROM transactions
                WHERE user_id = ? AND occurred_on BETWEEN ? AND ?
                  AND kind IN ({placeholders})
                ORDER BY occurred_on ASC, id ASC""",
            (user_id, start.isoformat(), end.isoformat(), *kinds),
        )
        return cur.fetchall()


def totals(user_id: int, start: date, end: date, currency: str = "som") -> dict[str, float]:
    """Bitta valyutadagi turlar bo'yicha jami — orqaga moslik uchun saqlangan."""
    return totals_by_currency(user_id, start, end).get(
        currency, {k: 0.0 for k in config.KINDS}
    )


def totals_by_currency(user_id: int, start: date, end: date) -> dict[str, dict[str, float]]:
    """{valyuta: {turi: summa}} — valyutalar birlashtirilmaydi (kurs yo'q)."""
    with get_conn() as conn:
        cur = conn.execute(
            """SELECT kind, currency, COALESCE(SUM(amount), 0) AS total
               FROM transactions
               WHERE user_id = ? AND occurred_on BETWEEN ? AND ?
               GROUP BY kind, currency""",
            (user_id, start.isoformat(), end.isoformat()),
        )
        result: dict[str, dict[str, float]] = {
            "som": {k: 0.0 for k in config.KINDS}
        }
        for row in cur.fetchall():
            bucket = result.setdefault(row["currency"], {k: 0.0 for k in config.KINDS})
            bucket[row["kind"]] = float(row["total"])
        return result


def totals_unified(user_id: int, start: date, end: date) -> dict:
    """Barcha valyutalarni asosiy valyutaga o'girib jamlaydi.

    Odamning hamyoni bitta: dollarda to'lasa ham pul o'sha umumiy
    mablag'idan chiqadi. `amount_base` — yozuv kiritilgan kundagi kurs
    bilan hisoblangan so'mdagi qiymat.
    """
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT kind, currency,
                      COALESCE(SUM(amount_base), 0) AS base,
                      COALESCE(SUM(amount), 0) AS orig,
                      COUNT(*) AS n
               FROM transactions
               WHERE user_id = ? AND occurred_on BETWEEN ? AND ?
               GROUP BY kind, currency""",
            (user_id, start.isoformat(), end.isoformat()),
        ).fetchall()

    totals = {k: 0.0 for k in config.KINDS}
    # Chet el valyutasidagi ulush — hisobotda alohida eslatib o'tiladi.
    foreign: dict[str, dict[str, float]] = {}
    for r in rows:
        totals[r["kind"]] = round(totals[r["kind"]] + float(r["base"]), 2)
        if r["currency"] != "som":
            bucket = foreign.setdefault(r["currency"], {"orig": 0.0, "base": 0.0,
                                                        "count": 0})
            bucket["orig"] = round(bucket["orig"] + float(r["orig"]), 2)
            bucket["base"] = round(bucket["base"] + float(r["base"]), 2)
            bucket["count"] += r["n"]
    return {"totals": totals, "foreign": foreign}


def by_category_unified(
    user_id: int, start: date, end: date, kind: str
) -> list[tuple[str, float, int]]:
    """Kategoriyalar kesimi — valyutalar asosiy valyutada birlashtirilgan."""
    with get_conn() as conn:
        cur = conn.execute(
            """SELECT category, SUM(amount_base) AS total, COUNT(*) AS cnt
               FROM transactions
               WHERE user_id = ? AND kind = ? AND occurred_on BETWEEN ? AND ?
               GROUP BY category ORDER BY total DESC""",
            (user_id, kind, start.isoformat(), end.isoformat()),
        )
        return [(r["category"], float(r["total"] or 0), int(r["cnt"]))
                for r in cur.fetchall()]


def by_category(
    user_id: int, start: date, end: date, kind: str, currency: str = "som"
) -> list[tuple[str, float, int]]:
    with get_conn() as conn:
        cur = conn.execute(
            """SELECT category, SUM(amount) AS total, COUNT(*) AS cnt
               FROM transactions
               WHERE user_id = ? AND kind = ? AND currency = ?
                 AND occurred_on BETWEEN ? AND ?
               GROUP BY category
               ORDER BY total DESC""",
            (user_id, kind, currency, start.isoformat(), end.isoformat()),
        )
        return [(r["category"], float(r["total"]), int(r["cnt"])) for r in cur.fetchall()]


def search_transactions(
    user_id: int,
    start: date,
    end: date,
    kind: str | None = None,
    currency: str | None = None,
    search: str | None = None,
    receipt_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Filtrlash, jamlash va sahifalash — hammasi SQL tomonida.

    Ilgari butun tarix Python'ga tortilib, u yerda filtrlanardi. Bir necha
    yillik yozuv to'planganda bu sezilarli yuk beradi.
    """
    where = ["user_id = ?", "occurred_on BETWEEN ? AND ?"]
    params: list = [user_id, start.isoformat(), end.isoformat()]

    if kind:
        where.append("kind = ?")
        params.append(kind)
    if currency:
        where.append("currency = ?")
        params.append(currency)
    if receipt_id:
        where.append("receipt_id = ?")
        params.append(receipt_id)
    if search and search.strip():
        needle = f"%{search.strip().lower()}%"
        where.append(
            "(LOWER(COALESCE(note,'')) LIKE ? OR LOWER(COALESCE(category,'')) LIKE ? "
            "OR LOWER(COALESCE(person,'')) LIKE ? OR LOWER(COALESCE(raw_text,'')) LIKE ?)")
        params += [needle] * 4

    clause = " AND ".join(where)
    with get_conn() as conn:
        total = int(conn.execute(
            f"SELECT COUNT(*) FROM transactions WHERE {clause}", params).fetchone()[0])
        totals = {
            r["currency"]: round(float(r["s"]), 2)
            for r in conn.execute(
                f"SELECT currency, SUM(amount) s FROM transactions "
                f"WHERE {clause} GROUP BY currency", params).fetchall()
        }
        items = conn.execute(
            f"""SELECT * FROM transactions WHERE {clause}
                ORDER BY occurred_on DESC, id DESC LIMIT ? OFFSET ?""",
            params + [limit, offset]).fetchall()

    return {"total_count": total, "totals": totals, "items": items}


def recent(user_id: int, limit: int = 10) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )
        return cur.fetchall()


def open_debts(user_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            """SELECT * FROM transactions
               WHERE user_id = ? AND kind IN (?, ?) AND settled = 0
               ORDER BY occurred_on ASC, id ASC""",
            (user_id, config.KIND_QARZ_BERDIM, config.KIND_QARZ_OLDIM),
        )
        return cur.fetchall()


def all_rows(user_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY occurred_on ASC, id ASC",
            (user_id,),
        )
        return cur.fetchall()


def rows_by_receipt(user_id: int, receipt_id: str) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            """SELECT * FROM transactions
               WHERE user_id = ? AND receipt_id = ?
               ORDER BY id ASC""",
            (user_id, receipt_id),
        )
        return cur.fetchall()


def delete_receipt(user_id: int, receipt_id: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM transactions WHERE user_id = ? AND receipt_id = ?",
            (user_id, receipt_id),
        )
        return cur.rowcount


# --------------------------------------------------------------------------- #
# Foydalanuvchilar, obuna va kirish huquqi
# --------------------------------------------------------------------------- #

def _now() -> datetime:
    return datetime.now(config.TZ)


def _today_str() -> str:
    """Kunlik limitlar mahalliy yarim tunda yangilanishi uchun Toshkent sanasi."""
    return _now().date().isoformat()


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    # Bazada mintaqasiz saqlanadi — solishtirish uchun mintaqa qo'shamiz.
    return dt if dt.tzinfo else dt.replace(tzinfo=config.TZ)


def get_or_create_user(user_id: int, first_name: str = "", username: str | None = None) -> sqlite3.Row:
    """Foydalanuvchini qaytaradi; birinchi marta ko'rilsa bepul sinov muddati
    bilan yaratadi."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            trial_ends = _now() + timedelta(days=config.TRIAL_DAYS)
            conn.execute(
                """INSERT INTO users (user_id, first_name, username, trial_ends_at, last_seen_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (user_id, first_name or "", username, trial_ends.isoformat(), _now().isoformat()),
            )
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        else:
            # Ism/username o'zgargan bo'lishi mumkin — yangilab turamiz.
            conn.execute(
                "UPDATE users SET first_name = ?, username = ?, last_seen_at = ? WHERE user_id = ?",
                (first_name or row["first_name"], username, _now().isoformat(), user_id),
            )
        return row


def access_status(user_id: int, first_name: str = "", username: str | None = None) -> dict:
    """Foydalanuvchining kirish holati.

    Qaytaradi: {"ok": bool, "status": str, "until": datetime|None, "days_left": int|None}
    status: owner | trial | subscribed | expired | blocked | not_allowed
    """
    if user_id in config.OWNER_IDS:
        return {"ok": True, "status": "owner", "until": None, "days_left": None}

    # ALLOWED_USER_IDS to'ldirilgan bo'lsa — yopiq rejim (sinov guruhi uchun).
    if config.ALLOWED_USER_IDS and user_id not in config.ALLOWED_USER_IDS:
        return {"ok": False, "status": "not_allowed", "until": None, "days_left": None}

    row = get_or_create_user(user_id, first_name, username)
    if row["blocked"]:
        return {"ok": False, "status": "blocked", "until": None, "days_left": None}

    now = _now()
    sub = _parse_dt(row["subscribed_until"])
    if sub and sub > now:
        return {"ok": True, "status": "subscribed", "until": sub,
                "days_left": max(0, (sub - now).days)}

    trial = _parse_dt(row["trial_ends_at"])
    if trial and trial > now:
        return {"ok": True, "status": "trial", "until": trial,
                "days_left": max(0, (trial - now).days)}

    return {"ok": False, "status": "expired", "until": sub or trial, "days_left": 0}


def grant_subscription(user_id: int, days: int) -> datetime:
    """Obunani uzaytiradi. Amaldagi obuna bor bo'lsa uning ustiga qo'shiladi."""
    with get_conn() as conn:
        row = conn.execute("SELECT subscribed_until FROM users WHERE user_id = ?",
                           (user_id,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
            base = _now()
        else:
            current = _parse_dt(row["subscribed_until"])
            base = current if current and current > _now() else _now()
        new_until = base + timedelta(days=days)
        conn.execute("UPDATE users SET subscribed_until = ? WHERE user_id = ?",
                     (new_until.isoformat(), user_id))
        return new_until


def _now_local() -> str:
    """Mahalliy vaqtdagi ISO muhri.

    SQLite'ning `datetime('now')` UTC beradi — admin panel bilan bir xil
    bo'lishi uchun vaqtni ochiq yozamiz.
    """
    return datetime.now(config.TZ).isoformat(timespec="seconds")


def add_subscription_request(user_id: int, plan_code: str, price: int) -> int:
    """Foydalanuvchi tarif tanlaganda chaqiriladi. Admin web panelda ko'rinadi.

    Takroriy bosishdan himoya: shu foydalanuvchining hal qilinmagan so'rovi
    bo'lsa, yangisi ochilmaydi — mavjudining tarifi yangilanadi."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM subscription_requests "
            "WHERE user_id = ? AND status = 'kutilmoqda' ORDER BY id DESC LIMIT 1",
            (user_id,),
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE subscription_requests SET plan_code = ?, price = ?, "
                "created_at = datetime('now') WHERE id = ?",
                (plan_code, price, row["id"]),
            )
            return int(row["id"])
        cur = conn.execute(
            "INSERT INTO subscription_requests (user_id, plan_code, price, created_at) "
            "VALUES (?,?,?,?)",
            (user_id, plan_code, price, _now_local()),
        )
        return int(cur.lastrowid)


def attach_payment_proof(request_id: int, file_id: str, kind: str = "rasm") -> bool:
    """Foydalanuvchi yuborgan to'lov chekini so'rovga biriktiradi.

    kind: 'rasm' yoki 'pdf' — admin panel chekni qanday ko'rsatishini
    shundan biladi.
    """
    with get_conn() as conn:
        cur = conn.execute(
            """UPDATE subscription_requests
               SET proof_file_id = ?, proof_at = ?, proof_kind = ?,
                   status = 'tekshiruvda'
               WHERE id = ? AND status IN ('kutilmoqda', 'tekshiruvda')""",
            (file_id, _now_local(), kind, request_id),
        )
        return cur.rowcount > 0


def get_request(request_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM subscription_requests WHERE id = ?", (request_id,)
        ).fetchone()


def open_request_for(user_id: int) -> sqlite3.Row | None:
    """Foydalanuvchining hal qilinmagan oxirgi so'rovi."""
    with get_conn() as conn:
        return conn.execute(
            """SELECT * FROM subscription_requests
               WHERE user_id = ? AND status IN ('kutilmoqda', 'tekshiruvda')
               ORDER BY id DESC LIMIT 1""",
            (user_id,),
        ).fetchone()


def pending_request_count() -> int:
    with get_conn() as conn:
        return int(conn.execute(
            "SELECT COUNT(*) FROM subscription_requests "
            "WHERE status IN ('kutilmoqda', 'tekshiruvda')"
        ).fetchone()[0])


# --------------------------------------------------------------------------- #
# Referal — do'st taklif qilish
# --------------------------------------------------------------------------- #

def set_referrer(user_id: int, referrer_id: int) -> bool:
    """Yangi foydalanuvchini taklif qilgan odamni belgilaydi.

    Faqat bir marta va faqat yangi (yozuvi yo'q) foydalanuvchi uchun —
    aks holda o'zini o'zi taklif qilish yoki qayta hisoblash mumkin bo'lardi.
    """
    if user_id == referrer_id:
        return False
    with get_conn() as conn:
        row = conn.execute(
            "SELECT referred_by, created_at FROM users WHERE user_id = ?",
            (user_id,)).fetchone()
        if row is None or row["referred_by"] is not None:
            return False
        if not conn.execute("SELECT 1 FROM users WHERE user_id = ?",
                            (referrer_id,)).fetchone():
            return False
        has_data = conn.execute(
            "SELECT 1 FROM transactions WHERE user_id = ? LIMIT 1", (user_id,)).fetchone()
        if has_data:
            return False
        conn.execute("UPDATE users SET referred_by = ? WHERE user_id = ?",
                     (referrer_id, user_id))
        return True


def add_bonus_days(user_id: int, days: int) -> datetime:
    """Bonus kunlarni amaldagi muddat ustiga qo'shadi (sinov yoki obuna)."""
    now = datetime.now(config.TZ)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT trial_ends_at, subscribed_until, bonus_days FROM users "
            "WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            return now
        sub = _parse_dt(row["subscribed_until"])
        if sub and sub > now:
            until = sub + timedelta(days=days)
            conn.execute("UPDATE users SET subscribed_until = ?, bonus_days = ? "
                         "WHERE user_id = ?",
                         (until.isoformat(timespec="seconds"),
                          (row["bonus_days"] or 0) + days, user_id))
        else:
            trial = _parse_dt(row["trial_ends_at"])
            base = trial if trial and trial > now else now
            until = base + timedelta(days=days)
            conn.execute("UPDATE users SET trial_ends_at = ?, bonus_days = ?, "
                         "warned_stage = 0 WHERE user_id = ?",
                         (until.isoformat(timespec="seconds"),
                          (row["bonus_days"] or 0) + days, user_id))
        return until


def referral_stats(user_id: int) -> dict:
    with get_conn() as conn:
        invited = int(conn.execute(
            "SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,)).fetchone()[0])
        bonus = conn.execute(
            "SELECT bonus_days FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return {"invited": invited, "bonus_days": (bonus["bonus_days"] if bonus else 0) or 0}


# --------------------------------------------------------------------------- #
# Byudjet
# --------------------------------------------------------------------------- #

def set_budget(user_id: int, category: str, amount: float, currency: str = "som") -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO budgets (user_id, category, amount, currency)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(user_id, category, currency)
               DO UPDATE SET amount = excluded.amount, notified = ''""",
            (user_id, category, float(amount), currency))


def delete_budget(user_id: int, category: str, currency: str = "som") -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM budgets WHERE user_id = ? AND category = ? AND currency = ?",
            (user_id, category, currency))
        return cur.rowcount > 0


def list_budgets(user_id: int) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM budgets WHERE user_id = ? ORDER BY category", (user_id,)
        ).fetchall()


def budget_status(user_id: int) -> list[dict]:
    """Har bir byudjet bo'yicha shu oyda qancha sarflanganini qaytaradi."""
    today = datetime.now(config.TZ).date()
    start = today.replace(day=1).isoformat()
    out = []
    with get_conn() as conn:
        for b in conn.execute("SELECT * FROM budgets WHERE user_id = ?",
                              (user_id,)).fetchall():
            spent = float(conn.execute(
                """SELECT COALESCE(SUM(amount), 0) FROM transactions
                   WHERE user_id = ? AND kind = ? AND category = ? AND currency = ?
                     AND occurred_on >= ?""",
                (user_id, config.KIND_CHIQIM, b["category"], b["currency"], start)
            ).fetchone()[0])
            limit = float(b["amount"])
            out.append({
                "category": b["category"], "limit": limit, "spent": spent,
                "currency": b["currency"],
                "percent": round(100 * spent / limit, 1) if limit else 0.0,
                "left": limit - spent,
                "notified": b["notified"] or "",
            })
    return sorted(out, key=lambda x: -x["percent"])


def mark_budget_notified(user_id: int, category: str, currency: str, tag: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE budgets SET notified = ? WHERE user_id = ? AND category = ? "
            "AND currency = ?", (tag, user_id, category, currency))


# --------------------------------------------------------------------------- #
# Eslatmalar va muddat ogohlantirishi
# --------------------------------------------------------------------------- #

def get_lang(user_id: int) -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT lang FROM users WHERE user_id = ?",
                           (user_id,)).fetchone()
        return (row["lang"] if row and row["lang"] else "uz")


def set_lang(user_id: int, lang: str) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET lang = ? WHERE user_id = ?", (lang, user_id))


def set_reminder_hour(user_id: int, hour: int | None) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET reminder_hour = ? WHERE user_id = ?",
                     (hour, user_id))


def get_reminder_hour(user_id: int) -> int | None:
    with get_conn() as conn:
        row = conn.execute("SELECT reminder_hour FROM users WHERE user_id = ?",
                           (user_id,)).fetchone()
        return row["reminder_hour"] if row else None


def users_for_reminder(hour: int) -> list[int]:
    """Shu soatga eslatma buyurgan va kirish huquqi bor foydalanuvchilar."""
    now = datetime.now(config.TZ)
    out = []
    with get_conn() as conn:
        for r in conn.execute(
                "SELECT * FROM users WHERE reminder_hour = ? AND blocked = 0",
                (hour,)).fetchall():
            if r["user_id"] in config.OWNER_IDS:
                out.append(r["user_id"])
                continue
            sub = _parse_dt(r["subscribed_until"])
            trial = _parse_dt(r["trial_ends_at"])
            if (sub and sub > now) or (trial and trial > now):
                out.append(r["user_id"])
    return out


def users_expiring(stages: tuple[int, ...] = (3, 1)) -> list[dict]:
    """Muddati tugashiga `stages` kun qolganlar. Har daraja bir marta.

    `warned_stage` — oxirgi yuborilgan ogohlantirish darajasi. Muddat
    uzaytirilsa nolga qaytariladi, shunda keyingi safar yana yuboriladi.
    """
    now = datetime.now(config.TZ)
    out = []
    with get_conn() as conn:
        for r in conn.execute("SELECT * FROM users WHERE blocked = 0").fetchall():
            if r["user_id"] in config.OWNER_IDS:
                continue
            sub = _parse_dt(r["subscribed_until"])
            trial = _parse_dt(r["trial_ends_at"])
            if sub and sub > now:
                expires, kind = sub, "obuna"
            elif trial and trial > now:
                expires, kind = trial, "sinov"
            else:
                continue
            # Yuqoriga yaxlitlaymiz: 1 kun 23 soat qolgan bo'lsa bu «2 kun»,
            # «1 kun» emas. Aks holda aynan 2 kunda 3 kunlik ogohlantirish
            # o'tkazib yuborilib, 1 kunligi erta ketardi.
            seconds = (expires - now).total_seconds()
            left = max(0, math.ceil(seconds / 86400))
            stage = next((s for s in sorted(stages) if left <= s), None)
            if stage is None:
                continue
            already = r["warned_stage"] or 0
            # Kichikroq daraja = shoshilinchroq. Faqat yangi darajada yuboramiz.
            if already and stage >= already:
                continue
            out.append({"user_id": r["user_id"], "first_name": r["first_name"],
                        "kind": kind, "days_left": left, "stage": stage,
                        "expires_at": expires})
    return out


def mark_warned(user_id: int, stage: int) -> None:
    with get_conn() as conn:
        conn.execute("UPDATE users SET warned_stage = ? WHERE user_id = ?",
                     (stage, user_id))


def day_summary(user_id: int, day: date) -> dict:
    """Kunlik eslatma uchun qisqa jamlanma."""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT kind, currency, COUNT(*) n, COALESCE(SUM(amount), 0) s
               FROM transactions WHERE user_id = ? AND occurred_on = ?
               GROUP BY kind, currency""",
            (user_id, day.isoformat())).fetchall()
    total = {"count": 0, "chiqim": {}, "kirim": {}}
    for r in rows:
        total["count"] += r["n"]
        if r["kind"] == config.KIND_CHIQIM:
            total["chiqim"][r["currency"]] = float(r["s"])
        elif r["kind"] == config.KIND_KIRIM:
            total["kirim"][r["currency"]] = float(r["s"])
    return total


# --------------------------------------------------------------------------- #
# Foydalanuvchi ma'lumotini butunlay o'chirish (M-2)
# --------------------------------------------------------------------------- #

def erase_user(user_id: int) -> dict:
    """Foydalanuvchining butun izini o'chiradi. Qaytarib bo'lmaydi."""
    with get_conn() as conn:
        tx = conn.execute("DELETE FROM transactions WHERE user_id = ?",
                          (user_id,)).rowcount
        usage = conn.execute("DELETE FROM usage_log WHERE user_id = ?",
                             (user_id,)).rowcount
        conn.execute("DELETE FROM budgets WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM subscription_requests WHERE user_id = ?", (user_id,))
        # Taklif qilganlar zanjiri uzilmasin — havola bo'sh qoladi.
        conn.execute("UPDATE users SET referred_by = NULL WHERE referred_by = ?",
                     (user_id,))
        conn.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
    return {"transactions": tx, "usage": usage}


def set_blocked(user_id: int, blocked: bool) -> bool:
    with get_conn() as conn:
        cur = conn.execute("UPDATE users SET blocked = ? WHERE user_id = ?",
                           (1 if blocked else 0, user_id))
        return cur.rowcount > 0


def list_users(limit: int = 50) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users ORDER BY last_seen_at DESC NULLS LAST LIMIT ?",
            (limit,),
        ).fetchall()


# --------------------------------------------------------------------------- #
# Token sarfi va kunlik limitlar
# --------------------------------------------------------------------------- #

def usage_begin(user_id: int, operation: str) -> int:
    """Amaldan OLDIN joy band qiladi va qator id'sini qaytaradi.

    Limit shu jadval bo'yicha sanalgani uchun band qilish chaqiruvdan oldin
    bo'lishi kerak — aks holda bir vaqtda yuborilgan ko'p so'rov limitni
    aylanib o'tib ketardi."""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO usage_log (user_id, day, operation) VALUES (?, ?, ?)",
            (user_id, _today_str(), operation),
        )
        return int(cur.lastrowid)


def usage_finish(usage_id: int, usage: dict | None) -> None:
    """Chaqiruv tugagach haqiqiy token sarfini yozadi."""
    if not usage:
        return
    with get_conn() as conn:
        conn.execute(
            """UPDATE usage_log SET model = ?, input_tokens = ?, output_tokens = ?,
                   cache_read = ?, cache_write = ?, cost_usd = ?
               WHERE id = ?""",
            (usage.get("model", ""), usage.get("input_tokens", 0),
             usage.get("output_tokens", 0), usage.get("cache_read", 0),
             usage.get("cache_write", 0), usage.get("cost_usd", 0.0), usage_id),
        )


def usage_cancel(usage_id: int) -> None:
    """Amal bajarilmagan bo'lsa (xatolik, tushunarsiz xabar) bandlikni bekor
    qiladi — foydalanuvchi bekorga limitini yo'qotmasin."""
    with get_conn() as conn:
        conn.execute("DELETE FROM usage_log WHERE id = ? AND cost_usd = 0", (usage_id,))


def count_today(user_id: int, operation: str) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM usage_log WHERE user_id = ? AND day = ? AND operation = ?",
            (user_id, _today_str(), operation),
        ).fetchone()
        return int(row["n"])


def usage_summary(user_id: int | None = None, days: int = 30) -> dict:
    """Sarf hisoboti. user_id berilmasa — butun tizim bo'yicha."""
    since = (_now() - timedelta(days=days)).date().isoformat()
    where = "day >= ?"
    params: list = [since]
    if user_id is not None:
        where += " AND user_id = ?"
        params.append(user_id)
    with get_conn() as conn:
        total = conn.execute(
            f"""SELECT COUNT(*) AS calls, COALESCE(SUM(cost_usd),0) AS cost,
                       COALESCE(SUM(input_tokens),0) AS inp,
                       COALESCE(SUM(output_tokens),0) AS out,
                       COALESCE(SUM(cache_read),0) AS cread
                FROM usage_log WHERE {where}""",
            params,
        ).fetchone()
        by_op = conn.execute(
            f"""SELECT operation, COUNT(*) AS calls, COALESCE(SUM(cost_usd),0) AS cost
                FROM usage_log WHERE {where} GROUP BY operation ORDER BY cost DESC""",
            params,
        ).fetchall()
        return {
            "days": days,
            "calls": int(total["calls"]),
            "cost_usd": float(total["cost"]),
            "input_tokens": int(total["inp"]),
            "output_tokens": int(total["out"]),
            "cache_read": int(total["cread"]),
            "by_operation": [
                {"operation": r["operation"], "calls": int(r["calls"]), "cost_usd": float(r["cost"])}
                for r in by_op
            ],
        }


def top_spenders(days: int = 30, limit: int = 10) -> list[dict]:
    since = (_now() - timedelta(days=days)).date().isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT u.user_id, u.first_name, u.username,
                      COUNT(*) AS calls, COALESCE(SUM(l.cost_usd),0) AS cost
               FROM usage_log l LEFT JOIN users u ON u.user_id = l.user_id
               WHERE l.day >= ? GROUP BY l.user_id ORDER BY cost DESC LIMIT ?""",
            (since, limit),
        ).fetchall()
        return [
            {"user_id": r["user_id"], "first_name": r["first_name"] or "",
             "username": r["username"], "calls": int(r["calls"]), "cost_usd": float(r["cost"])}
            for r in rows
        ]


def user_count() -> dict:
    with get_conn() as conn:
        now_iso = _now().isoformat()
        r = conn.execute(
            """SELECT COUNT(*) AS total,
                      SUM(CASE WHEN blocked = 1 THEN 1 ELSE 0 END) AS blocked,
                      SUM(CASE WHEN subscribed_until > ? THEN 1 ELSE 0 END) AS subscribed,
                      SUM(CASE WHEN (subscribed_until IS NULL OR subscribed_until <= ?)
                                AND trial_ends_at > ? THEN 1 ELSE 0 END) AS trial
               FROM users""",
            (now_iso, now_iso, now_iso),
        ).fetchone()
        return {"total": int(r["total"] or 0), "blocked": int(r["blocked"] or 0),
                "subscribed": int(r["subscribed"] or 0), "trial": int(r["trial"] or 0)}


def rows_for_ai(user_id: int, limit: int) -> list[sqlite3.Row]:
    """Savolga javob berish uchun oxirgi yozuvlar (eng yangilari birinchi olinadi)."""
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY occurred_on DESC, id DESC LIMIT ?",
            (user_id, limit),
        )
        return list(reversed(cur.fetchall()))
