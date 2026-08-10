"""Shaxsiy moliya boti — Telegram + Anthropic Claude.

Ishga tushirish:  python bot.py
"""

from __future__ import annotations

import asyncio
import base64
import csv
import io
import logging
import uuid
from functools import wraps

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    MenuButtonDefault,
    MenuButtonWebApp,
    ReplyKeyboardMarkup,
    Update,
    WebAppInfo,
)
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import ai
import config
import db
import reports

logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("hisobchi")

# Anthropic API qo'llaydigan rasm turlari.
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
PDF_TYPE = "application/pdf"

# Albom (bir vaqtda yuborilgan bir nechta rasm) to'planishini kutish vaqti.
ALBUM_WAIT_SECONDS = 3.0

HELP_TEXT = """👋 <b>Shaxsiy hisobchi</b>

<b>1. Oddiy tilda yozing</b>
• <code>obedga 45 ming</code>
• <code>taksi 20k, kofe 25 ming</code>
• <code>oylik tushdi 8 mln</code>
• <code>Aliga 500 ming qarz berdim</code>
• <code>kecha dorixonaga 90 ming</code>
• <code>Diyorga 100 dollar oylik berdim</code> — dollar ham qo'llab-quvvatlanadi

<b>2. Chek rasmini yuboring</b> 📷
Chekdagi har bir mahsulot o'qilib, kategoriyalarga ajratilib bazaga
yoziladi, jami summa hisoblanib chekdagi «JAMI» bilan tekshiriladi.

<i>Uzun chek kadrga sig'masa</i> — qismlarga bo'lib suratga oling va
hammasini <b>birdan</b> (albom qilib) yuboring. Yoki «🧾 Uzun chek»
tugmasini bosib, bitta-bitta yuborib «✅ Tayyor» deng.

<i>Maslahat:</i> eng aniq natija uchun rasmni <b>Fayl</b> sifatida
yuboring — Telegram uni siqmaydi.

<b>3. Savol bering</b>
<code>bu oy eng ko'p nimaga pul ketdi?</code>

<b>Buyruqlar:</b>
/bugun /kecha /hafta /oy /otganoy /yil — hisobotlar
/oxirgi — oxirgi yozuvlar
/qarz — ochiq qarzlar
/chek — uzun chekni qismlab yuborish
/ochir 12 — 12-yozuvni o'chirish
/yopdim 12 — qarzni yopilgan deb belgilash
/csv — barcha yozuvlarni fayl qilib olish
/qollanma — to'liq foydalanish yo'riqnomasi
/id — Telegram ID'ingiz"""


GUIDE_TEXT = """📖 <b>FOYDALANISH YO'RIQNOMASI</b>

━━━━━━━━━━━━━━━━━━━━
<b>1️⃣ XARAJAT VA KIRIM YOZISH</b>

Shunchaki oddiy tilda yozing — bot summani, turini va
kategoriyani o'zi aniqlaydi.

<b>Sonlarni qanday yozish mumkin:</b>
• <code>ming</code> yoki <code>k</code> = 1 000 → <code>45 ming</code>, <code>20k</code>
• <code>mln</code>, <code>million</code>, <code>lim</code> = 1 000 000 → <code>1.5 mln</code>
• Bo'sh joy bilan → <code>1 200 000</code>
• Birliksiz kichik son ming deb olinadi → <code>obedga 50</code> = 50 000

<b>Dollar bilan yozish:</b>
<code>$100</code>, <code>50 dollar</code>, <code>200 dollar oylik berdim</code>
→ ming qoidasi qo'llanmaydi, son aynan yoziladi. Hisobotlarda so'm va
dollar alohida-alohida ko'rsatiladi (kurs orqali qo'shilmaydi).

<b>Bitta xabarda bir nechta yozuv:</b>
<code>taksi 20k, kofe 25 ming, non 8 ming</code>
→ 3 ta alohida yozuv saqlanadi

<b>Kirim:</b>
<code>oylik tushdi 8 mln</code>
<code>sotuvdan 500 ming kirdi</code>

<b>Qarz:</b>
<code>Aliga 500 ming qarz berdim</code>
<code>akamdan 1 mln qarz oldim</code>
→ kim kimga qarzdorligi alohida kuzatiladi

<b>Sanani ko'rsatish:</b>
<code>kecha dorixonaga 90 ming</code>
<code>1-avgustda benzin 100 ming</code>
Sana aytilmasa — bugungi kun.

━━━━━━━━━━━━━━━━━━━━
<b>2️⃣ CHEK RASMINI YUBORISH</b> 📷

Chek suratini yuborsangiz, bot undagi <b>har bir mahsulotni</b>
o'qib, kategoriyalarga ajratib bazaga yozadi.

<b>Oddiy chek:</b> shunchaki rasmni yuboring.

<b>Uzun chek (kadrga sig'masa) — 2 ta usul:</b>

<i>A) Albom qilib yuborish (eng qulay)</i>
Chekni qismlarga bo'lib suratga oling → galereyadan
hammasini belgilang → birdan yuboring. Bot ularni
bitta chek deb qabul qiladi.

<i>B) Bitta-bitta yuborish</i>
«🧾 Uzun chek» tugmasini bosing → qismlarni ketma-ket
yuboring → «✅ Tayyor» bosing.

Chek natijasidan keyin «➕ Chek davomi bor» tugmasi
ham bor — qism esdan chiqsa, o'shani bosib qo'shasiz.

⚠️ <b>Qismlar bir-birini takrorlasa ham bo'ladi</b> — bir xil
qator ikki rasmda ko'rinsa, bir marta hisoblanadi.

━━━━━━━━━━━━━━━━━━━━
<b>3️⃣ ANIQLIK VA TEKSHIRUV</b> ✅

Bot mahsulotlar summasini <b>o'zi hisoblaydi</b> (AI emas) va
chekdagi «JAMI» bilan solishtiradi:

✅ <b>Mos</b> — summa to'g'ri o'qilgan, ishonch yuqori
⚠️ <b>Farqli</b> — nomuvofiqlik bor. Bunda bot chekni
   avtomatik <b>qayta o'qiydi</b>. Baribir farq qolsa,
   sizga farq miqdori ko'rsatiladi — «📋 To'liq ro'yxat»
   dan tekshiring.
ℹ️ <b>Jami ko'rinmadi</b> — chekda yakuniy summa yo'q,
   tekshirib bo'lmadi.

<b>Rasm sifati uchun maslahatlar:</b>
• Rasmni <b>Fayl</b> sifatida yuboring (Telegram siqmaydi)
• Yorug' joyda, to'g'ridan-to'g'ri suratga oling
• Chek tekis yotsin, burchaklari ko'rinsin
• Soyalar va yorqin nur tushmasin

━━━━━━━━━━━━━━━━━━━━
<b>4️⃣ XATONI TUZATISH</b> 🔧

Har bir yozuv ostida tugmalar bor:
• <b>✏️ Kategoriya</b> — kategoriyani almashtirish
• <b>🗑 O'chirish</b> — yozuvni o'chirish

Chek uchun:
• <b>📋 To'liq ro'yxat</b> — barcha mahsulotlar raqami bilan
• <b>🗑 Chekni o'chirish</b> — butun chekni bir bosishda

Raqam bo'yicha o'chirish: <code>/ochir 12</code>

━━━━━━━━━━━━━━━━━━━━
<b>5️⃣ HISOBOTLAR</b> 📊

Tugmalar yoki buyruqlar orqali:
/bugun /kecha /hafta /oy /otganoy /yil

Har birida: kirim, chiqim, farq, kategoriyalar
foizli diagramma bilan va kunlik o'rtacha.

/oxirgi — oxirgi 12 ta yozuv
/qarz — ochiq qarzlar ro'yxati
/yopdim 12 — qarzni yopilgan deb belgilash

━━━━━━━━━━━━━━━━━━━━
<b>6️⃣ SAVOL BERISH</b> 💬

Shunchaki savol yozing:
<code>bu oy eng ko'p nimaga pul ketdi?</code>
<code>o'tgan haftaga nisbatan qancha ko'p sarfladim?</code>
<code>kuniga o'rtacha qancha ketyapti?</code>
<code>kimga qancha qarzim bor?</code>

Jamlanmalarni dastur aniq hisoblaydi, AI faqat
tushuntiradi — shuning uchun sonlar to'g'ri bo'ladi.

━━━━━━━━━━━━━━━━━━━━
<b>7️⃣ EKSPORT</b> 📤

/csv — barcha yozuvlar Excel'da ochiladigan fayl
ko'rinishida. Chek yozuvlari «chek» ustuni bo'yicha
guruhlangan bo'ladi."""


# --------------------------------------------------------------------------- #
# Ruxsat
# --------------------------------------------------------------------------- #

def private_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user is None:
            return
        if user.id not in config.ALLOWED_USER_IDS:
            log.warning("Ruxsatsiz urinish: id=%s username=%s", user.id, user.username)
            if update.effective_message:
                await update.effective_message.reply_text(
                    f"Bu shaxsiy bot.\nSizning ID: {user.id}"
                )
            return
        return await func(update, context)

    return wrapper


# --------------------------------------------------------------------------- #
# Klaviaturalar
# --------------------------------------------------------------------------- #

def main_menu() -> ReplyKeyboardMarkup:
    """Har chaqiruvda quriladi — WEBAPP_URL ishga tushirilgandan keyin
    qo'shilsa, botni qayta ishga tushirmasdan ham tugma paydo bo'ladi."""
    rows = [
        ["📊 Bugun", "📅 Hafta", "🗓 Oy"],
        ["🧾 Oxirgi", "🤝 Qarzlar", "📈 Yil"],
        ["🧾 Uzun chek", "📤 CSV", "📖 Qo'llanma"],
    ]
    keyboard = [[KeyboardButton(text) for text in row] for row in rows]
    if config.WEBAPP_URL:
        keyboard.append([
            KeyboardButton(
                "📊 Boshqaruv paneli", web_app=WebAppInfo(url=config.WEBAPP_URL)
            )
        ])
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        input_field_placeholder="Xarajat yozing yoki chek rasmini yuboring…",
    )

COLLECT_MENU = ReplyKeyboardMarkup(
    [["✅ Tayyor", "❌ Bekor"]],
    resize_keyboard=True,
    input_field_placeholder="Chekning qolgan qismlarini yuboring…",
)


def entry_keyboard(tx_ids: list[int], kind: str | None = None) -> InlineKeyboardMarkup | None:
    if len(tx_ids) == 1:
        tx = tx_ids[0]
        row = [
            InlineKeyboardButton("✏️ Kategoriya", callback_data=f"c:{tx}"),
            InlineKeyboardButton("🗑 O'chirish", callback_data=f"d:{tx}"),
        ]
        buttons = [row]
        # Kirim/chiqim almashtirish faqat oddiy yozuvlar uchun — qarz turlari
        # shaxs maydoniga bog'liq bo'lgani uchun bu yerda almashtirilmaydi.
        if kind in (config.KIND_CHIQIM, config.KIND_KIRIM):
            other = config.KIND_KIRIM if kind == config.KIND_CHIQIM else config.KIND_CHIQIM
            buttons.append([
                InlineKeyboardButton(
                    f"🔄 {config.KIND_LABELS[other]}ga almashtirish",
                    callback_data=f"t:{tx}",
                )
            ])
        return InlineKeyboardMarkup(buttons)
    if tx_ids:
        payload = "D:" + ",".join(map(str, tx_ids))
        # Telegram callback_data uchun chegara — 64 bayt.
        if len(payload.encode()) <= 64:
            return InlineKeyboardMarkup(
                [[InlineKeyboardButton("🗑 Hammasini o'chirish", callback_data=payload)]]
            )
    return None


def receipt_keyboard(receipt_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📋 To'liq ro'yxat", callback_data=f"L:{receipt_id}")],
            [InlineKeyboardButton("➕ Chek davomi bor", callback_data=f"A:{receipt_id}")],
            [InlineKeyboardButton("🗑 Chekni o'chirish", callback_data=f"R:{receipt_id}")],
        ]
    )


def category_keyboard(tx_id: int, kind: str) -> InlineKeyboardMarkup:
    cats = config.categories_for(kind)
    buttons, row = [], []
    for idx, name in enumerate(cats):
        icon = config.CATEGORY_ICONS.get(name, "•")
        row.append(InlineKeyboardButton(f"{icon} {name}", callback_data=f"s:{tx_id}:{idx}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("⬅️ Bekor", callback_data=f"x:{tx_id}")])
    return InlineKeyboardMarkup(buttons)


# --------------------------------------------------------------------------- #
# Buyruqlar
# --------------------------------------------------------------------------- #

def _help_text() -> str:
    if config.WEBAPP_URL:
        return HELP_TEXT + (
            "\n\n<b>4. Grafik boshqaruv paneli</b> 📊\n"
            "«📊 Boshqaruv paneli» tugmasi (yoki pastdagi menyu tugmasi) — "
            "diagramma, filtrlar va qidiruv bilan to'liq interaktiv panel."
        )
    return HELP_TEXT


@private_only
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        _help_text(), parse_mode=ParseMode.HTML, reply_markup=main_menu()
    )


@private_only
async def cmd_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for chunk in _split_message(GUIDE_TEXT):
        await update.effective_message.reply_text(
            chunk, parse_mode=ParseMode.HTML, reply_markup=main_menu()
        )


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(
        f"Telegram ID: {user.id}\n"
        f"Uni .env faylidagi ALLOWED_USER_IDS ga yozing."
    )


def _period_command(period: str):
    @private_only
    async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = reports.summary_text(update.effective_user.id, period)
        await update.effective_message.reply_text(text, parse_mode=ParseMode.HTML)

    return handler


@private_only
async def cmd_recent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        reports.recent_text(update.effective_user.id, 12), parse_mode=ParseMode.HTML
    )


@private_only
async def cmd_debts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(
        reports.debts_text(update.effective_user.id), parse_mode=ParseMode.HTML
    )


@private_only
async def cmd_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].lstrip("#").isdigit():
        await update.message.reply_text("Foydalanish: /ochir 12")
        return
    tx_id = int(context.args[0].lstrip("#"))
    ok = db.delete_transaction(update.effective_user.id, tx_id)
    await update.message.reply_text(
        f"🗑 #{tx_id} o'chirildi." if ok else f"#{tx_id} topilmadi."
    )


@private_only
async def cmd_settle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].lstrip("#").isdigit():
        await update.message.reply_text("Foydalanish: /yopdim 12")
        return
    tx_id = int(context.args[0].lstrip("#"))
    ok = db.settle_debt(update.effective_user.id, tx_id)
    await update.message.reply_text(
        f"✅ #{tx_id} qarzi yopildi." if ok else f"#{tx_id} ochiq qarzlar orasida topilmadi."
    )


@private_only
async def cmd_csv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = db.all_rows(update.effective_user.id)
    if not rows:
        await update.effective_message.reply_text("Eksport qilish uchun yozuv yo'q.")
        return

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["id", "sana", "turi", "summa", "valyuta", "kategoriya", "izoh",
         "shaxs", "yopilgan", "chek"]
    )
    for r in rows:
        writer.writerow([
            r["id"], r["occurred_on"], r["kind"], r["amount"],
            r["currency"] if "currency" in r.keys() else "som",
            r["category"], r["note"], r["person"] or "", r["settled"],
            r["receipt_id"] or "",
        ])

    data = io.BytesIO(buf.getvalue().encode("utf-8-sig"))
    data.name = "hisobot.csv"
    await update.effective_message.reply_document(
        document=data, filename="hisobot.csv", caption=f"{len(rows)} ta yozuv."
    )


# --------------------------------------------------------------------------- #
# Chek: rasm yuklash va tahlil
# --------------------------------------------------------------------------- #

# Albom bo'lib kelayotgan rasmlar: media_group_id -> {"images", "caption", "task"}
_albums: dict[str, dict] = {}
# «Uzun chek» rejimi: user_id -> {"images": [...], "caption": str}
_collect: dict[int, dict] = {}
# Oxirgi chek — «davomi bor» tugmasi uchun: user_id -> {"receipt_id", "images", "caption"}
_last_receipt: dict[int, dict] = {}


class ImageError(Exception):
    """Faylni yuklab bo'lmadi — sabab foydalanuvchiga ko'rsatiladi."""


def _guess_pdf(document) -> bool:
    """Ba'zi mijozlar PDF'ni noto'g'ri MIME turi bilan yuboradi."""
    name = (document.file_name or "").lower()
    return (document.mime_type or "").lower() == PDF_TYPE or name.endswith(".pdf")


async def _download_receipt_file(context, message) -> tuple[str, str]:
    """Xabardan chek faylini (base64, media_type) ko'rinishida oladi.

    Rasm ham, PDF ham qabul qilinadi.
    """
    if message.photo:
        # photo[-1] — eng katta o'lchamdagi nusxa.
        tg_file = await context.bot.get_file(message.photo[-1].file_id)
        media_type = "image/jpeg"
        limit = config.MAX_IMAGE_BYTES
    elif message.document:
        doc = message.document
        if _guess_pdf(doc):
            media_type, limit = PDF_TYPE, config.MAX_PDF_BYTES
        else:
            media_type = (doc.mime_type or "").lower()
            limit = config.MAX_IMAGE_BYTES
            if media_type not in SUPPORTED_IMAGE_TYPES:
                raise ImageError(
                    "Bu fayl turi qo'llab-quvvatlanmaydi.\n"
                    "Chekni rasm (JPG/PNG) yoki PDF ko'rinishida yuboring."
                )
        if (doc.file_size or 0) > limit:
            raise ImageError(
                f"Fayl juda katta ({(doc.file_size or 0) // 1_000_000} MB, "
                f"chegara {limit // 1_000_000} MB)."
            )
        tg_file = await context.bot.get_file(doc.file_id)
    else:
        raise ImageError("Chek fayli topilmadi.")

    raw = bytes(await tg_file.download_as_bytearray())
    if len(raw) > limit:
        raise ImageError(
            f"Fayl juda katta ({len(raw) // 1_000_000} MB, "
            f"chegara {limit // 1_000_000} MB)."
        )
    return base64.standard_b64encode(raw).decode(), media_type


async def _process_receipt(update: Update, context, images: list, caption: str):
    """Chek rasm(lar)ini o'qib, mahsulotlarni bazaga yozadi va tahlil qaytaradi."""
    message = update.effective_message
    user_id = update.effective_user.id

    if len(images) > config.MAX_RECEIPT_PARTS:
        await message.reply_text(
            f"Bitta chek uchun ko'pi bilan {config.MAX_RECEIPT_PARTS} ta rasm "
            f"yuborish mumkin (siz {len(images)} ta yubordingiz)."
        )
        return

    qism = f" ({len(images)} ta qism)" if len(images) > 1 else ""
    status = await message.reply_text(f"🔍 Chek o'qilmoqda{qism}…")
    await context.bot.send_chat_action(message.chat_id, ChatAction.TYPING)

    try:
        data = await ai.parse_receipt(images, today=reports.today(), caption=caption)
    except Exception:
        log.exception("Chekni o'qishda xatolik")
        await status.edit_text(
            "⚠️ Chekni o'qishda xatolik yuz berdi. Birozdan keyin urinib ko'ring."
        )
        return

    if not data["oqildi"]:
        hint = data["izoh_matni"] or (
            "Chekni o'qib bo'lmadi. Yorug'roq, to'g'ridan-to'g'ri tushirilgan "
            "surat yuboring."
        )
        await status.edit_text(f"🤔 {reports.esc(hint)}", parse_mode=ParseMode.HTML)
        return

    receipt_id = uuid.uuid4().hex[:10]
    shop = data["dokon"]
    db.add_many([
        {
            "user_id": user_id,
            "kind": config.KIND_CHIQIM,
            "amount": item["summa"],
            "category": item["kategoriya"],
            "note": item["nomi"],
            "person": None,
            "occurred_on": data["sana"],
            "raw_text": f"chek: {shop}" if shop else "chek",
            "receipt_id": receipt_id,
        }
        for item in data["mahsulotlar"]
    ])

    start, end, _ = reports.period_range("bugun")
    day_total = db.totals(user_id, start, end)[config.KIND_CHIQIM]

    _last_receipt[user_id] = {
        "receipt_id": receipt_id,
        "images": images,
        "caption": caption,
    }

    await status.edit_text(
        reports.receipt_text(data, day_total),
        parse_mode=ParseMode.HTML,
        reply_markup=receipt_keyboard(receipt_id),
    )


async def _flush_album(key: str, update: Update, context):
    """Albomdagi barcha rasmlar kelib bo'lgach, ularni birgalikda tahlil qiladi."""
    try:
        await asyncio.sleep(ALBUM_WAIT_SECONDS)
    except asyncio.CancelledError:
        return
    bucket = _albums.pop(key, None)
    if not bucket or not bucket["images"]:
        return
    await _process_receipt(update, context, bucket["images"], bucket["caption"])


@private_only
async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user_id = update.effective_user.id
    caption = message.caption or ""

    try:
        image = await _download_receipt_file(context, message)
    except ImageError as exc:
        await message.reply_text(f"⚠️ {exc}")
        return
    except Exception:
        log.exception("Chek faylini yuklab olishda xatolik")
        await message.reply_text("⚠️ Faylni yuklab olishda xatolik yuz berdi.")
        return

    # 1) «Uzun chek» rejimi — qismlarni yig'amiz.
    if user_id in _collect:
        bucket = _collect[user_id]
        bucket["images"].append(image)
        if caption and not bucket["caption"]:
            bucket["caption"] = caption
        await message.reply_text(
            f"✅ {len(bucket['images'])}-qism qabul qilindi.\n"
            "Yana yuboring yoki «✅ Tayyor» bosing.",
            reply_markup=COLLECT_MENU,
        )
        return

    # 2) Albom — bir vaqtda yuborilgan bir nechta rasm bitta chek deb qaraladi.
    if message.media_group_id:
        key = str(message.media_group_id)
        bucket = _albums.setdefault(key, {"images": [], "caption": "", "task": None})
        bucket["images"].append(image)
        if caption and not bucket["caption"]:
            bucket["caption"] = caption
        if bucket["task"]:
            bucket["task"].cancel()
        bucket["task"] = asyncio.create_task(_flush_album(key, update, context))
        return

    # 3) Bitta rasm.
    await _process_receipt(update, context, [image], caption)


@private_only
async def cmd_collect_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _collect[update.effective_user.id] = {"images": [], "caption": ""}
    await update.effective_message.reply_text(
        "🧾 <b>Uzun chek rejimi</b>\n\n"
        "Chekni qismlarga bo'lib suratga oling va ketma-ket yuboring "
        "(yuqoridan pastga). Qismlar bir-birini biroz takrorlasa ham "
        "bo'ladi — takroriy qatorlar bir marta hisoblanadi.\n\n"
        "Hammasi tayyor bo'lgach «✅ Tayyor» bosing.",
        parse_mode=ParseMode.HTML,
        reply_markup=COLLECT_MENU,
    )


@private_only
async def cmd_collect_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bucket = _collect.pop(update.effective_user.id, None)
    if not bucket or not bucket["images"]:
        await update.effective_message.reply_text(
            "Hech qanday rasm yuborilmadi.", reply_markup=main_menu()
        )
        return
    await update.effective_message.reply_text(
        f"📥 {len(bucket['images'])} ta qism qabul qilindi.", reply_markup=main_menu()
    )
    await _process_receipt(update, context, bucket["images"], bucket["caption"])


@private_only
async def cmd_collect_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _collect.pop(update.effective_user.id, None)
    await update.effective_message.reply_text("Bekor qilindi.", reply_markup=main_menu())


# --------------------------------------------------------------------------- #
# Asosiy matn handleri
# --------------------------------------------------------------------------- #

# Menyu tugmalari matn sifatida keladi — shu yerda tegishli handlerga yo'naltiriladi.
MENU_ACTIONS = {
    "📊 Bugun": _period_command("bugun"),
    "📅 Hafta": _period_command("hafta"),
    "🗓 Oy": _period_command("oy"),
    "📈 Yil": _period_command("yil"),
    "🧾 Oxirgi": cmd_recent,
    "🤝 Qarzlar": cmd_debts,
    "📤 CSV": cmd_csv,
    "📖 Qo'llanma": cmd_guide,
    "🧾 Uzun chek": cmd_collect_start,
    "✅ Tayyor": cmd_collect_done,
    "❌ Bekor": cmd_collect_cancel,
}


@private_only
async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    text = (message.text or "").strip()
    if not text:
        return

    action = MENU_ACTIONS.get(text)
    if action:
        await action(update, context)
        return

    user_id = update.effective_user.id

    # «Uzun chek» rejimida yozilgan matn — chek uchun izoh.
    if user_id in _collect:
        _collect[user_id]["caption"] = text
        await message.reply_text(
            "📝 Izoh saqlandi. Chek qismlarini yuborishda davom eting.",
            reply_markup=COLLECT_MENU,
        )
        return

    await context.bot.send_chat_action(message.chat_id, ChatAction.TYPING)

    try:
        parsed = await ai.parse_message(text, today=reports.today())
    except Exception:
        log.exception("AI tahlilida xatolik")
        await message.reply_text("⚠️ AI bilan bog'lanishda xatolik. Birozdan keyin urinib ko'ring.")
        return

    niyat = parsed["niyat"]

    if niyat == "savol":
        try:
            rows = db.rows_for_ai(user_id, config.QA_MAX_ROWS)
            answer = await ai.answer_question(text, rows, today=reports.today())
        except Exception:
            log.exception("AI javobida xatolik")
            await message.reply_text("⚠️ Javob tayyorlashda xatolik yuz berdi.")
            return
        await message.reply_text(answer)
        return

    if niyat != "yozuv" or not parsed["yozuvlar"]:
        hint = parsed.get("izoh_matni") or (
            "Tushunmadim. Summani aniq yozing, masalan: <code>obedga 45 ming</code>"
        )
        await message.reply_text(f"🤔 {reports.esc(hint)}", parse_mode=ParseMode.HTML)
        return

    saved_ids: list[int] = []
    for item in parsed["yozuvlar"]:
        tx_id = db.add_transaction(
            user_id=user_id,
            kind=item["turi"],
            amount=item["summa"],
            category=item["kategoriya"],
            note=item["izoh"],
            person=item["shaxs"],
            occurred_on=item["sana"],
            raw_text=text,
            currency=item["valyuta"],
        )
        saved_ids.append(tx_id)

    body = reports.saved_text(parsed["yozuvlar"])

    # Bugungi umumiy chiqim — qisqa kontekst uchun, har bir valyuta alohida
    start, end, _ = reports.period_range("bugun")
    day_by_currency = db.totals_by_currency(user_id, start, end)
    day_parts = [
        reports.fmt_money(amounts[config.KIND_CHIQIM], cur)
        for cur, amounts in day_by_currency.items()
        if amounts[config.KIND_CHIQIM]
    ]
    if day_parts:
        body += f"\n\n<i>Bugungi chiqim: {' + '.join(day_parts)}</i>"

    single_kind = parsed["yozuvlar"][0]["turi"] if len(saved_ids) == 1 else None
    await message.reply_text(
        body, parse_mode=ParseMode.HTML,
        reply_markup=entry_keyboard(saved_ids, single_kind),
    )


# --------------------------------------------------------------------------- #
# Tugmalar
# --------------------------------------------------------------------------- #

def _split_message(text: str, limit: int = 3900) -> list[str]:
    """Uzun xabarni Telegram chegarasiga sig'adigan bo'laklarga bo'ladi."""
    if len(text) <= limit:
        return [text]
    chunks, current = [], ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > limit:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line
    if current:
        chunks.append(current)
    return chunks


async def on_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id
    if user_id not in config.ALLOWED_USER_IDS:
        await query.answer("Ruxsat yo'q.", show_alert=True)
        return

    data = query.data or ""

    if data.startswith("d:"):
        tx_id = int(data[2:])
        db.delete_transaction(user_id, tx_id)
        await query.answer("O'chirildi")
        await query.edit_message_text("🗑 Yozuv o'chirildi.")
        return

    if data.startswith("D:"):
        ids = [int(x) for x in data[2:].split(",") if x.isdigit()]
        for tx_id in ids:
            db.delete_transaction(user_id, tx_id)
        await query.answer("O'chirildi")
        await query.edit_message_text(f"🗑 {len(ids)} ta yozuv o'chirildi.")
        return

    # --- Chek tugmalari ---

    if data.startswith("R:"):
        receipt_id = data[2:]
        removed = db.delete_receipt(user_id, receipt_id)
        _last_receipt.pop(user_id, None)
        await query.answer("O'chirildi")
        await query.edit_message_text(f"🗑 Chek o'chirildi ({removed} ta yozuv).")
        return

    if data.startswith("L:"):
        receipt_id = data[2:]
        rows = db.rows_by_receipt(user_id, receipt_id)
        await query.answer()
        for chunk in _split_message(reports.receipt_items_text(rows)):
            await query.message.reply_text(chunk, parse_mode=ParseMode.HTML)
        return

    if data.startswith("A:"):
        receipt_id = data[2:]
        last = _last_receipt.get(user_id)
        if not last or last["receipt_id"] != receipt_id:
            await query.answer(
                "Bu chek rasmlari saqlanmagan. «🧾 Uzun chek» bilan qaytadan yuboring.",
                show_alert=True,
            )
            return
        # Eski yozuvlar olib tashlanadi — chek to'liq holda qayta o'qiladi.
        db.delete_receipt(user_id, receipt_id)
        _collect[user_id] = {"images": list(last["images"]), "caption": last["caption"]}
        await query.answer()
        await query.edit_message_text(
            f"➕ Chekning qolgan qismlarini yuboring "
            f"({len(last['images'])} ta qism allaqachon bor).\n"
            "Tugagach «✅ Tayyor» bosing — chek boshidan qayta hisoblanadi."
        )
        await query.message.reply_text(
            "Qolgan qismlarni kutyapman…", reply_markup=COLLECT_MENU
        )
        return

    # --- Kategoriya tugmalari ---

    if data.startswith("c:"):
        tx_id = int(data[2:])
        row = db.get_transaction(user_id, tx_id)
        if not row:
            await query.answer("Yozuv topilmadi", show_alert=True)
            return
        await query.answer()
        await query.edit_message_reply_markup(category_keyboard(tx_id, row["kind"]))
        return

    if data.startswith("s:"):
        _, raw_id, raw_idx = data.split(":")
        tx_id, idx = int(raw_id), int(raw_idx)
        row = db.get_transaction(user_id, tx_id)
        if not row:
            await query.answer("Yozuv topilmadi", show_alert=True)
            return
        cats = config.categories_for(row["kind"])
        if not 0 <= idx < len(cats):
            await query.answer("Noto'g'ri kategoriya", show_alert=True)
            return
        db.update_category(user_id, tx_id, cats[idx])
        await query.answer("Yangilandi")
        row = db.get_transaction(user_id, tx_id)
        await query.edit_message_text(
            "✏️ Kategoriya yangilandi\n\n" + reports.transaction_line(row),
            parse_mode=ParseMode.HTML,
            reply_markup=entry_keyboard([tx_id], row["kind"]),
        )
        return

    if data.startswith("x:"):
        tx_id = int(data[2:])
        row = db.get_transaction(user_id, tx_id)
        await query.answer()
        await query.edit_message_reply_markup(
            entry_keyboard([tx_id], row["kind"] if row else None)
        )
        return

    # --- Turini (kirim/chiqim) almashtirish ---

    if data.startswith("t:"):
        tx_id = int(data[2:])
        row = db.get_transaction(user_id, tx_id)
        if not row or row["kind"] not in (config.KIND_CHIQIM, config.KIND_KIRIM):
            await query.answer("Bu yozuv turini almashtirib bo'lmaydi", show_alert=True)
            return
        new_kind = config.KIND_KIRIM if row["kind"] == config.KIND_CHIQIM else config.KIND_CHIQIM
        new_category = config.fallback_category(new_kind)
        db.update_kind(user_id, tx_id, new_kind, new_category)
        await query.answer("Turi yangilandi")
        row = db.get_transaction(user_id, tx_id)
        await query.edit_message_text(
            f"🔄 {config.KIND_LABELS[new_kind]}ga almashtirildi\n\n"
            + reports.transaction_line(row)
            + "\n\n<i>Kategoriyani ham to'g'rilash uchun «✏️ Kategoriya» bosing.</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=entry_keyboard([tx_id], new_kind),
        )
        return

    await query.answer()


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Handler xatoligi", exc_info=context.error)


# --------------------------------------------------------------------------- #
# Ishga tushirish
# --------------------------------------------------------------------------- #

BOT_COMMANDS = [
    ("start", "Boshlash va yordam"),
    ("qollanma", "To'liq foydalanish yo'riqnomasi"),
    ("chek", "Uzun chekni qismlab yuborish"),
    ("bugun", "Bugungi hisobot"),
    ("kecha", "Kechagi hisobot"),
    ("hafta", "Shu haftalik hisobot"),
    ("oy", "Shu oylik hisobot"),
    ("otganoy", "O'tgan oylik hisobot"),
    ("yil", "Yillik hisobot"),
    ("oxirgi", "Oxirgi yozuvlar"),
    ("qarz", "Ochiq qarzlar"),
    ("ochir", "Yozuvni o'chirish: /ochir 12"),
    ("yopdim", "Qarzni yopish: /yopdim 12"),
    ("csv", "Barcha yozuvlarni fayl qilib olish"),
    ("id", "Telegram ID'ingiz"),
]


async def _post_init(app: Application) -> None:
    """Telegramdagi «/» menyusini to'ldiradi — buyruqlarni eslash shart emas."""
    from telegram import BotCommand

    await app.bot.set_my_commands([BotCommand(c, d) for c, d in BOT_COMMANDS])

    # Pastki chap burchakdagi doimiy menyu tugmasi — Mini App'ni bir bosishda ochadi.
    if config.WEBAPP_URL:
        await app.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Boshqaruv paneli",
                web_app=WebAppInfo(url=config.WEBAPP_URL),
            )
        )
        log.info("Mini App menyu tugmasi yoqildi: %s", config.WEBAPP_URL)
    else:
        await app.bot.set_chat_menu_button(menu_button=MenuButtonDefault())


def main() -> None:
    missing = config.missing_settings()
    if missing:
        raise SystemExit(
            ".env faylida quyidagilar yo'q: " + ", ".join(missing)
        )
    if not config.ALLOWED_USER_IDS:
        log.warning(
            "ALLOWED_USER_IDS bo'sh — bot hech kimni kiritmaydi. "
            "Botga /id yozib, ID'ingizni .env ga qo'shing."
        )

    db.init()

    app = (
        Application.builder()
        .token(config.TELEGRAM_TOKEN)
        .post_init(_post_init)
        .build()
    )

    app.add_handler(CommandHandler(["start", "yordam", "help"], cmd_start))
    app.add_handler(CommandHandler(["qollanma", "guide"], cmd_guide))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("bugun", _period_command("bugun")))
    app.add_handler(CommandHandler("kecha", _period_command("kecha")))
    app.add_handler(CommandHandler("hafta", _period_command("hafta")))
    app.add_handler(CommandHandler("oy", _period_command("oy")))
    app.add_handler(CommandHandler("otganoy", _period_command("otgan_oy")))
    app.add_handler(CommandHandler("yil", _period_command("yil")))
    app.add_handler(CommandHandler("oxirgi", cmd_recent))
    app.add_handler(CommandHandler("qarz", cmd_debts))
    app.add_handler(CommandHandler("ochir", cmd_delete))
    app.add_handler(CommandHandler("yopdim", cmd_settle))
    app.add_handler(CommandHandler("csv", cmd_csv))
    app.add_handler(CommandHandler("chek", cmd_collect_start))
    app.add_handler(CommandHandler("tayyor", cmd_collect_done))
    app.add_handler(CommandHandler("bekor", cmd_collect_cancel))
    app.add_handler(CallbackQueryHandler(on_callback))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, on_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)

    log.info("Bot ishga tushdi. To'xtatish: Ctrl+C")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
