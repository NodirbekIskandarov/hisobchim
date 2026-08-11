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
import secrets
import time
from datetime import date, timedelta
from urllib.parse import parse_qsl

import csv
import io

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

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

    # Kirish huquqi bot bilan BIR XIL qoidada tekshiriladi: ega — cheksiz,
    # boshqalar — bepul sinov yoki amaldagi obuna.
    access = db.access_status(user_id, user.get("first_name", ""), user.get("username"))
    if not access["ok"]:
        detail = {
            "blocked": "Hisobingiz bloklangan.",
            "not_allowed": "Bot hozircha yopiq sinovda.",
        }.get(access["status"], "Bepul muddat tugadi — obuna kerak.")
        raise HTTPException(403, detail)

    return {
        "user_id": user_id,
        "first_name": user.get("first_name", ""),
        "access": access,
    }


def current_user(x_telegram_init_data: str = Header(default="")) -> dict:
    """FastAPI dependency: har bir himoyalangan endpoint shu orqali autentifikatsiya qiladi."""
    user = _validate_init_data(x_telegram_init_data)
    _check_rate(user["user_id"])
    return user


# --------------------------------------------------------------------------- #
# Eksport tokeni
#
# Ilgari CSV havolasi initData'ni URL parametrida olib yurar edi. Bunday
# havola brauzer tarixida va proxy loglarida 24 soat davomida amal qilib
# qolardi. Endi: avval POST bilan bir martalik token olinadi, u 60 soniya
# yashaydi va ishlatilgach darhol o'chadi.
# --------------------------------------------------------------------------- #

EXPORT_TOKEN_TTL = 60
_export_tokens: dict[str, tuple[int, float]] = {}


def _issue_export_token(user_id: int) -> str:
    now = time.time()
    for tok, (_, exp) in list(_export_tokens.items()):
        if exp < now:
            _export_tokens.pop(tok, None)
    token = secrets.token_urlsafe(32)
    _export_tokens[token] = (user_id, now + EXPORT_TOKEN_TTL)
    return token


def _consume_export_token(token: str) -> int:
    entry = _export_tokens.pop(token, None)
    if not entry:
        raise HTTPException(401, "Havola eskirgan — panelni yangilab qayta urining")
    user_id, expires = entry
    if expires < time.time():
        raise HTTPException(401, "Havola eskirgan — panelni yangilab qayta urining")
    return user_id


# --------------------------------------------------------------------------- #
# So'rov chegarasi — bitta foydalanuvchi serverni band qilib qo'ymasin
# --------------------------------------------------------------------------- #

RATE_LIMIT = 90          # daqiqasiga so'rov
_rate: dict[int, list[float]] = {}


def _check_rate(user_id: int) -> None:
    now = time.time()
    hits = [t for t in _rate.get(user_id, []) if now - t < 60]
    if len(hits) >= RATE_LIMIT:
        raise HTTPException(429, "Juda ko'p so'rov. Bir daqiqadan keyin urinib ko'ring.")
    hits.append(now)
    _rate[user_id] = hits
    # Xotira o'smasin: eskirgan yozuvlarni vaqti-vaqti bilan tozalaymiz.
    if len(_rate) > 2000:
        for uid in [u for u, ts in _rate.items() if not ts or now - ts[-1] > 300]:
            _rate.pop(uid, None)


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
    access = user.get("access") or {}
    until = access.get("until")
    return {
        "user_id": user["user_id"],
        "first_name": user["first_name"],
        "subscription": {
            "status": access.get("status", "trial"),
            "days_left": access.get("days_left"),
            "until": until.isoformat() if until else None,
        },
        "currency": config.CURRENCY,
        "categories": config.ALL_CATEGORIES,
        "category_icons": config.CATEGORY_ICONS,
        "currency_symbols": config.CURRENCY_SYMBOLS,
        "kind_icons": config.KIND_ICONS,
        "kind_labels": config.KIND_LABELS,
        "categories_by_kind": {
            config.KIND_CHIQIM: config.EXPENSE_CATEGORIES,
            config.KIND_KIRIM: config.INCOME_CATEGORIES,
            config.KIND_QARZ_BERDIM: config.DEBT_CATEGORIES,
            config.KIND_QARZ_OLDIM: config.DEBT_CATEGORIES,
        },
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
    receipt_id: str | None = None,
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

    # Filtrlash, tartiblash va sahifalash SQL tomonida — foydalanuvchida
    # bir necha yillik yozuv to'planganda ham tez ishlashi kerak.
    result = db.search_transactions(
        user["user_id"], start_d, end_d, kind=kind, currency=currency,
        search=search, receipt_id=receipt_id, limit=limit, offset=offset)

    return {
        "total_count": result["total_count"],
        "totals": result["totals"],
        "items": [_serialize_tx(r) for r in result["items"]],
    }


@app.delete("/api/transactions/{tx_id}")
def api_delete_transaction(tx_id: int, user: dict = Depends(current_user)):
    ok = db.delete_transaction(user["user_id"], tx_id)
    if not ok:
        raise HTTPException(404, "Yozuv topilmadi")
    return {"deleted": True}


def _serialize_tx(row) -> dict:
    return {
        "id": row["id"], "date": row["occurred_on"], "kind": row["kind"],
        "amount": row["amount"], "currency": row["currency"],
        "category": row["category"], "note": row["note"],
        "person": row["person"], "receipt_id": row["receipt_id"],
        "settled": bool(row["settled"]),
    }


class TxUpdate(BaseModel):
    category: str | None = None
    # Faqat kirim<->chiqim almashtirish — bot.py'dagi "🔄 Turini almashtirish"
    # tugmasi bilan bir xil cheklov (qarz turlari shaxs maydoniga bog'liq,
    # bu yerda o'zgartirilmaydi).
    kind: str | None = None


@app.patch("/api/transactions/{tx_id}")
def api_update_transaction(tx_id: int, body: TxUpdate, user: dict = Depends(current_user)):
    row = db.get_transaction(user["user_id"], tx_id)
    if not row:
        raise HTTPException(404, "Yozuv topilmadi")

    if body.kind and body.kind != row["kind"]:
        if row["kind"] not in (config.KIND_CHIQIM, config.KIND_KIRIM) or \
           body.kind not in (config.KIND_CHIQIM, config.KIND_KIRIM):
            raise HTTPException(400, "Bu yozuv turini almashtirib bo'lmaydi")
        new_category = body.category or config.fallback_category(body.kind)
        if new_category not in config.categories_for(body.kind):
            raise HTTPException(400, "Noto'g'ri kategoriya")
        db.update_kind(user["user_id"], tx_id, body.kind, new_category)
    elif body.category:
        if body.category not in config.categories_for(row["kind"]):
            raise HTTPException(400, "Noto'g'ri kategoriya")
        db.update_category(user["user_id"], tx_id, body.category)

    return _serialize_tx(db.get_transaction(user["user_id"], tx_id))


@app.post("/api/debts/{tx_id}/settle")
def api_settle_debt(tx_id: int, user: dict = Depends(current_user)):
    ok = db.settle_debt(user["user_id"], tx_id)
    if not ok:
        raise HTTPException(404, "Ochiq qarzlar orasida topilmadi")
    return {"settled": True}


class TxCreate(BaseModel):
    kind: str
    amount: float = Field(gt=0)
    currency: str = "som"
    category: str
    note: str = ""
    person: str | None = None
    date: str | None = None


@app.post("/api/transactions", status_code=201)
def api_create_transaction(body: TxCreate, user: dict = Depends(current_user)):
    if body.kind not in config.KINDS:
        raise HTTPException(400, "Noto'g'ri turi")
    currency = config.normalize_currency(body.currency)
    category = config.normalize_category(body.kind, body.category)
    person = (body.person or "").strip() or None
    if body.kind in config.DEBT_KINDS and not person:
        raise HTTPException(400, "Qarz uchun shaxs ismi kerak")
    if body.kind not in config.DEBT_KINDS:
        person = None
    occurred_on = _parse_date(body.date, reports.today()).isoformat()

    tx_id = db.add_transaction(
        user_id=user["user_id"], kind=body.kind, amount=body.amount,
        category=category, note=body.note.strip()[:120], person=person,
        occurred_on=occurred_on, raw_text="[boshqaruv panelidan qo'lda qo'shildi]",
        currency=currency,
    )
    return _serialize_tx(db.get_transaction(user["user_id"], tx_id))


@app.post("/api/export/token")
def api_export_token(user: dict = Depends(current_user)):
    """Bir martalik, 60 soniya yashaydigan yuklab olish tokeni."""
    return {"token": _issue_export_token(user["user_id"]), "ttl": EXPORT_TOKEN_TTL}


@app.get("/api/export.csv")
def api_export_csv(token: str = Query(...)):
    user_id = _consume_export_token(token)
    rows = db.all_rows(user_id)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["id", "sana", "turi", "summa", "valyuta", "kategoriya", "izoh",
         "shaxs", "yopilgan", "chek"]
    )
    for r in rows:
        writer.writerow([
            r["id"], r["occurred_on"], r["kind"], r["amount"], r["currency"],
            r["category"], r["note"], r["person"] or "", r["settled"],
            r["receipt_id"] or "",
        ])
    content = buf.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=hisobot.csv"},
    )


# --------------------------------------------------------------------------- #
# Statik fayllar (frontend) — API'dan keyin ro'yxatga olinadi, aks holda
# "/" barcha "/api/*" so'rovlarini ham qamrab olib qo'yishi mumkin.
# --------------------------------------------------------------------------- #

app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")
