"""SQLite bilan ishlash qatlami. Bitta foydalanuvchi uchun mo'ljallangan, lekin
user_id bo'yicha ajratilgan — kerak bo'lsa bir nechta odam ishlatishi mumkin."""

from __future__ import annotations

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
"""

# Eski bazalarga keyin qo'shilgan ustunlar. CREATE TABLE IF NOT EXISTS mavjud
# jadvalni o'zgartirmaydi, shuning uchun qo'lda tekshiramiz.
MIGRATIONS = [
    ("receipt_id", "ALTER TABLE transactions ADD COLUMN receipt_id TEXT"),
    ("currency", "ALTER TABLE transactions ADD COLUMN currency TEXT NOT NULL DEFAULT 'som'"),
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


# --------------------------------------------------------------------------- #
# Yozish
# --------------------------------------------------------------------------- #

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
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO transactions
               (user_id, kind, amount, category, note, person, occurred_on,
                raw_text, receipt_id, currency)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, kind, float(amount), category, note, person,
             occurred_on, raw_text, receipt_id, currency),
        )
        return int(cur.lastrowid)


def add_many(rows: list[dict]) -> list[int]:
    """Bir nechta yozuvni bitta tranzaksiyada saqlaydi (chek uchun)."""
    ids: list[int] = []
    with get_conn() as conn:
        for r in rows:
            cur = conn.execute(
                """INSERT INTO transactions
                   (user_id, kind, amount, category, note, person, occurred_on,
                    raw_text, receipt_id, currency)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (r["user_id"], r["kind"], float(r["amount"]), r["category"],
                 r.get("note", ""), r.get("person"), r["occurred_on"],
                 r.get("raw_text", ""), r.get("receipt_id"), r.get("currency", "som")),
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
