"""Telegram Mini App uchun API server — grafik boshqaruv paneli.

bot.py bilan bir xil SQLite bazasini o'qiydi (db.py orqali), alohida
jarayon sifatida ishga tushiriladi: uvicorn webapp:app

Xavfsizlik: har bir so'rov Telegram'ning WebApp initData imzosini
tekshiradi (HMAC-SHA256, bot tokeni bilan) — shu orqali foydalanuvchi
Telegram ichidan haqiqiy kirganini va boshqa foydalanuvchi ma'lumotini
so'ramayotganini kafolatlaydi. Bot ALLOWED_USER_IDS ro'yxati bu yerda
ham qo'llanadi.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import date, timedelta
from urllib.parse import parse_qsl

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import config
import db
import reports

app = FastAPI(title="Hisobchi AI — boshqaruv paneli")

# initData 24 soatdan eski bo'lsa rad etiladi (Telegram tavsiyasi).
INIT_DATA_MAX_AGE = 24 * 3600


# --------------------------------------------------------------------------- #
# Telegram WebApp initData tekshiruvi
# --------------------------------------------------------------------------- #

def _validate_init_data(init_data: str) -> dict:
    """initData imzosini tekshiradi va ichidagi foydalanuvchi ma'lumotini qaytaradi.

    Noto'g'ri imzo yoki eskirgan bo'lsa HTTPException ko'taradi.
    Algoritm: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    if not init_data:
        raise HTTPException(401, "initData yo'q")

    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        raise HTTPException(401, "initData formati noto'g'ri")

    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise HTTPException(401, "hash yo'q")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", config.TELEGRAM_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise HTTPException(401, "imzo mos kelmadi")

    try:
        auth_date = int(pairs.get("auth_date", "0"))
    except ValueError:
        auth_date = 0
    if auth_date <= 0 or (time.time() - auth_date) > INIT_DATA_MAX_AGE:
        raise HTTPException(401, "initData eskirgan — Mini App'ni qayta oching")

    try:
        user = json.loads(pairs.get("user", "{}"))
    except json.JSONDecodeError:
        raise HTTPException(401, "foydalanuvchi ma'lumoti noto'g'ri")

    user_id = user.get("id")
    if not isinstance(user_id, int):
        raise HTTPException(401, "foydalanuvchi ID topilmadi")

    if user_id not in config.ALLOWED_USER_IDS:
        raise HTTPException(403, "Bu shaxsiy panel — sizga ruxsat yo'q")

    return {"user_id": user_id, "first_name": user.get("first_name", "")}


def current_user(x_telegram_init_data: str = Header(default="")) -> dict:
    """FastAPI dependency: har bir himoyalangan endpoint shu orqali autentifikatsiya qiladi."""
    return _validate_init_data(x_telegram_init_data)


# --------------------------------------------------------------------------- #
# Sana oralig'ini hisoblash (dashboard uchun — oldinga/orqaga navigatsiya)
# --------------------------------------------------------------------------- #

def _compute_range(period: str, ref: date) -> tuple[date, date, str]:
    if period == "hafta":
        start = ref - timedelta(days=ref.weekday())
        end = start + timedelta(days=6)
        if start.month == end.month:
            label = f"{start.day}–{end.day} {reports.UZ_MONTHS[start.month - 1]}"
        else:
            label = (
                f"{start.day} {reports.UZ_MONTHS[start.month - 1]} – "
                f"{end.day} {reports.UZ_MONTHS[end.month - 1]}"
            )
        return start, end, label
    if period == "oy":
        start = ref.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        end = next_month - timedelta(days=1)
        label = f"{reports.UZ_MONTHS[ref.month - 1].capitalize()} {ref.year}"
        return start, end, label
    if period == "yil":
        start = ref.replace(month=1, day=1)
        end = ref.replace(month=12, day=31)
        return start, end, f"{ref.year}-yil"
    # "kun"
    label = f"{ref.day}-{reports.UZ_MONTHS[ref.month - 1]}"
    return ref, ref, label


def _parse_date(raw: str | None, default: date) -> date:
    if not raw:
        return default
    try:
        return date.fromisoformat(raw)
    except ValueError:
        raise HTTPException(400, f"Noto'g'ri sana: {raw}")


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #

@app.get("/api/me")
def api_me(user: dict = Depends(current_user)):
    return {
        "user_id": user["user_id"],
        "first_name": user["first_name"],
        "currency": config.CURRENCY,
        "categories": config.ALL_CATEGORIES,
        "category_icons": config.CATEGORY_ICONS,
        "currency_symbols": config.CURRENCY_SYMBOLS,
        "kind_icons": config.KIND_ICONS,
        "kind_labels": config.KIND_LABELS,
    }


@app.get("/api/summary")
def api_summary(
    period: str = Query("oy", pattern="^(kun|hafta|oy|yil)$"),
    ref: str | None = None,
    user: dict = Depends(current_user),
):
    ref_date = _parse_date(ref, reports.today())
    start, end, label = _compute_range(period, ref_date)

    by_cur = db.totals_by_currency(user["user_id"], start, end)
    currencies = sorted(by_cur.keys(), key=lambda c: c != "som")

    result = {}
    for cur in currencies:
        t = by_cur[cur]
        chiqim_cats = db.by_category(user["user_id"], start, end, config.KIND_CHIQIM, cur)
        kirim_cats = db.by_category(user["user_id"], start, end, config.KIND_KIRIM, cur)
        result[cur] = {
            "kirim": t[config.KIND_KIRIM],
            "chiqim": t[config.KIND_CHIQIM],
            "farq": t[config.KIND_KIRIM] - t[config.KIND_CHIQIM],
            "qarz_berdim": t[config.KIND_QARZ_BERDIM],
            "qarz_oldim": t[config.KIND_QARZ_OLDIM],
            "chiqim_kategoriyalari": [
                {"kategoriya": c, "summa": s, "soni": n} for c, s, n in chiqim_cats
            ],
            "kirim_kategoriyalari": [
                {"kategoriya": c, "summa": s, "soni": n} for c, s, n in kirim_cats
            ],
        }

    return {
        "period": period,
        "ref": ref_date.isoformat(),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "label": label,
        "currencies": currencies,
        "by_currency": result,
    }


@app.get("/api/debts")
def api_debts(user: dict = Depends(current_user)):
    rows = db.open_debts(user["user_id"])

    def _group(kind: str) -> dict:
        items = [r for r in rows if r["kind"] == kind]
        by_cur: dict[str, list[dict]] = {}
        for r in items:
            cur = r["currency"]
            by_cur.setdefault(cur, []).append({
                "id": r["id"], "person": r["person"] or "noma'lum",
                "amount": r["amount"], "date": r["occurred_on"],
                "note": r["note"],
            })
        totals = {cur: round(sum(i["amount"] for i in lst), 2) for cur, lst in by_cur.items()}
        return {"totals": totals, "items": by_cur}

    return {
        "qarz_berdim": _group(config.KIND_QARZ_BERDIM),
        "qarz_oldim": _group(config.KIND_QARZ_OLDIM),
    }


@app.get("/api/transactions")
def api_transactions(
    start: str | None = None,
    end: str | None = None,
    currency: str | None = None,
    kind: str | None = None,
    search: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: dict = Depends(current_user),
):
    start_d = _parse_date(start, date(2000, 1, 1))
    end_d = _parse_date(end, reports.today())
    if kind and kind not in config.KINDS:
        raise HTTPException(400, "Noto'g'ri turi")
    if currency and currency not in config.SUPPORTED_CURRENCIES:
        raise HTTPException(400, "Noto'g'ri valyuta")

    all_rows = db.list_range(user["user_id"], start_d, end_d, [kind] if kind else None)
    if currency:
        all_rows = [r for r in all_rows if r["currency"] == currency]
    if search:
        needle = search.strip().lower()
        all_rows = [
            r for r in all_rows
            if needle in (r["note"] or "").lower()
            or needle in (r["category"] or "").lower()
            or needle in (r["person"] or "").lower()
            or needle in (r["raw_text"] or "").lower()
        ]

    totals: dict[str, float] = {}
    for r in all_rows:
        totals[r["currency"]] = round(totals.get(r["currency"], 0.0) + r["amount"], 2)

    all_rows = sorted(all_rows, key=lambda r: (r["occurred_on"], r["id"]), reverse=True)
    page = all_rows[offset:offset + limit]

    return {
        "total_count": len(all_rows),
        "totals": totals,
        "items": [
            {
                "id": r["id"], "date": r["occurred_on"], "kind": r["kind"],
                "amount": r["amount"], "currency": r["currency"],
                "category": r["category"], "note": r["note"],
                "person": r["person"], "receipt_id": r["receipt_id"],
            }
            for r in page
        ],
    }


@app.delete("/api/transactions/{tx_id}")
def api_delete_transaction(tx_id: int, user: dict = Depends(current_user)):
    ok = db.delete_transaction(user["user_id"], tx_id)
    if not ok:
        raise HTTPException(404, "Yozuv topilmadi")
    return {"deleted": True}


# --------------------------------------------------------------------------- #
# Statik fayllar (frontend) — API'dan keyin ro'yxatga olinadi, aks holda
# "/" barcha "/api/*" so'rovlarini ham qamrab olib qo'yishi mumkin.
# --------------------------------------------------------------------------- #

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")
