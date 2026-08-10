"""SQLite bilan ishlash qatlami. Bitta foydalanuvchi uchun mo'ljallangan, lekin
user_id bo'yicha ajratilgan — kerak bo'lsa bir nechta odam ishlatishi mumkin."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import date
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


def rows_for_ai(user_id: int, limit: int) -> list[sqlite3.Row]:
    """Savolga javob berish uchun oxirgi yozuvlar (eng yangilari birinchi olinadi)."""
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM transactions WHERE user_id = ? ORDER BY occurred_on DESC, id DESC LIMIT ?",
            (user_id, limit),
        )
        return list(reversed(cur.fetchall()))
