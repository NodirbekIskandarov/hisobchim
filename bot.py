"""Shaxsiy moliya boti — Telegram + Anthropic Claude.

Ishga tushirish:  python bot.py
"""

from __future__ import annotations

import asyncio
import base64
import csv
import io
import logging
import time
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
/obuna — obuna tariflari
/holat — obuna holati va bugungi limitlar"""


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

SUBSCRIBE_TEXT = (
    "⏳ <b>Bepul muddat tugadi</b>\n\n"
    "Botdan foydalanishni davom ettirish uchun obuna kerak.\n"
    "Quyidagi tariflardan birini tanlang yoki <b>{contact}</b> ga yozing.\n\n"
    "<i>Ma'lumotlaringiz saqlanib turibdi — obunadan keyin hammasi joyida bo'ladi.</i>"
)


def _support_contact() -> str:
    return config.SUPPORT_CONTACT or "administrator"


def private_only(func):
    """Kirish nazorati: ega — cheksiz; boshqalar — bepul sinov yoki obuna."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user is None:
            return
        access = db.access_status(user.id, user.first_name or "", user.username)
        context.user_data["access"] = access

        if access["ok"]:
            return await func(update, context)

        msg = update.effective_message
        if msg is None:
            return
        if access["status"] == "blocked":
            await msg.reply_text("🚫 Hisobingiz bloklangan.")
        elif access["status"] == "not_allowed":
            log.info("Yopiq rejim: id=%s username=%s", user.id, user.username)
            await msg.reply_text(
                f"Bot hozircha yopiq sinovda.\nSizning ID: {user.id}"
            )
        else:  # expired
            await msg.reply_text(
                SUBSCRIBE_TEXT.format(contact=reports.esc(_support_contact())),
                parse_mode=ParseMode.HTML,
                reply_markup=plans_keyboard(),
            )
        return

    return wrapper


def owner_only(func):
    """Faqat bot egalari uchun (admin buyruqlari)."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user is None or user.id not in config.OWNER_IDS:
            return
        return await func(update, context)

    return wrapper


# --------------------------------------------------------------------------- #
# Kunlik limitlar — bitta foydalanuvchi cheksiz xarajat keltirmasligi uchun.
# Egalarga qo'llanmaydi.
# --------------------------------------------------------------------------- #

LIMITS = {
    "matn": (config.LIMIT_TEXT_PER_DAY, "matnli yozuv"),
    "chek": (config.LIMIT_RECEIPT_PER_DAY, "chek"),
    "savol": (config.LIMIT_QA_PER_DAY, "savol"),
}


async def check_quota(update: Update, context: ContextTypes.DEFAULT_TYPE,
                      operation: str) -> int | None:
    """Limitni tekshiradi va joy band qiladi.

    Qaytaradi: usage_log qatorining id'si (amal tugagach yozish uchun),
    yoki limit tugagan bo'lsa None."""
    user_id = update.effective_user.id
    if user_id in config.OWNER_IDS:
        return db.usage_begin(user_id, operation)

    limit, label = LIMITS[operation]
    used = db.count_today(user_id, operation)
    if used >= limit:
        await update.effective_message.reply_text(
            f"⏳ Bugungi <b>{label}</b> limiti tugadi ({limit} ta).\n"
            "Ertaga yarim tundan keyin yangilanadi.",
            parse_mode=ParseMode.HTML,
        )
        return None
    return db.usage_begin(user_id, operation)


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
        ["💎 Obuna"],
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
    access = context.user_data.get("access") or {}
    text = _help_text()

    # Yangi foydalanuvchiga sinov muddatini darrov aytamiz — kutilmagan
    # "muddat tugadi" xabari bilan to'qnashmasin.
    if access.get("status") == "trial":
        text += (
            f"\n\n🎁 <b>Bepul sinov: {access['days_left']} kun qoldi.</b>\n"
            "Holatni ko'rish: /holat"
        )
    elif access.get("status") == "subscribed":
        text += f"\n\n✅ <b>Obuna faol</b> — {access['days_left']} kun qoldi."

    await update.effective_message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=main_menu()
    )


@private_only
async def cmd_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for chunk in _split_message(GUIDE_TEXT):
        await update.effective_message.reply_text(
            chunk, parse_mode=ParseMode.HTML, reply_markup=main_menu()
        )


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Faqat bot egasi uchun. OWNER_IDS hali bo'sh bo'lsa — birinchi
    sozlash uchun ochiq qoladi, aks holda egani aniqlab bo'lmaydi."""
    user = update.effective_user
    if user is None:
        return
    if config.OWNER_IDS and user.id not in config.OWNER_IDS:
        return  # oddiy foydalanuvchiga buyruq umuman mavjud emasdek
    await update.message.reply_text(
        f"Telegram ID: {user.id}\n"
        f"Uni .env faylidagi OWNER_IDS ga yozing."
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

class TTLStore:
    """Muddati bilan o'zini tozalaydigan lug'at.

    Chek rasmlari base64 ko'rinishida xotirada turadi (bittasi bir necha MB).
    Oddiy dict bilan 1000 foydalanuvchida bu gigabaytlarga o'sib, serverni
    xotirasiz qoldirardi. Bu yerda har bir yozuv muddati o'tgach o'chiriladi
    va umumiy soni ham cheklangan."""

    def __init__(self, ttl_seconds: int, max_items: int):
        self._data: dict = {}
        self._ttl = ttl_seconds
        self._max = max_items

    def _purge(self) -> None:
        now = time.monotonic()
        for key in [k for k, (exp, _) in self._data.items() if exp < now]:
            self._data.pop(key, None)
        # Chegaradan oshsa — eng eskisidan boshlab chiqaramiz.
        while len(self._data) > self._max:
            oldest = min(self._data, key=lambda k: self._data[k][0])
            self._data.pop(oldest, None)

    def get(self, key, default=None):
        self._purge()
        item = self._data.get(key)
        if item is None:
            return default
        # Foydalanilgan yozuvning muddati yangilanadi.
        self._data[key] = (time.monotonic() + self._ttl, item[1])
        return item[1]

    def set(self, key, value) -> None:
        self._data[key] = (time.monotonic() + self._ttl, value)
        self._purge()

    def setdefault(self, key, default):
        existing = self.get(key)
        if existing is not None:
            return existing
        self.set(key, default)
        return default

    def pop(self, key, default=None):
        item = self._data.pop(key, None)
        return default if item is None else item[1]

    def __contains__(self, key) -> bool:
        return self.get(key) is not None

    def __len__(self) -> int:
        self._purge()
        return len(self._data)


# Albom bo'lib kelayotgan rasmlar: media_group_id -> {"images", "caption", "task"}
_albums = TTLStore(ttl_seconds=300, max_items=200)
# «Uzun chek» rejimi: user_id -> {"images": [...], "caption": str}
_collect = TTLStore(ttl_seconds=1800, max_items=200)
# Oxirgi chek — «davomi bor» tugmasi uchun: user_id -> {"receipt_id", "images", "caption"}
# Qisqa muddat: bu faqat "davomi bor" tugmasi uchun kerak, uzoq saqlash shart emas.
_last_receipt = TTLStore(ttl_seconds=900, max_items=100)


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

    usage_id = await check_quota(update, context, "chek")
    if usage_id is None:
        return

    qism = f" ({len(images)} ta qism)" if len(images) > 1 else ""
    status = await message.reply_text(f"🔍 Chek o'qilmoqda{qism}…")
    await context.bot.send_chat_action(message.chat_id, ChatAction.TYPING)

    try:
        data = await ai.parse_receipt(images, today=reports.today(), caption=caption)
    except Exception:
        log.exception("Chekni o'qishda xatolik")
        db.usage_cancel(usage_id)
        await status.edit_text(
            "⚠️ Chekni o'qishda xatolik yuz berdi. Birozdan keyin urinib ko'ring."
        )
        return

    db.usage_finish(usage_id, data.get("_usage"))

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

    _last_receipt.set(user_id, {
        "receipt_id": receipt_id,
        "images": images,
        "caption": caption,
    })

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
        bucket = _collect.get(user_id)
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
    _collect.set(update.effective_user.id, {"images": [], "caption": ""})
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

# Menyu tugmalari matn sifatida keladi — shu yerda tegishli handlerga
# yo'naltiriladi. Lug'at fayl OXIRIDA to'ldiriladi (build_menu_actions),
# chunki bu yerda hali hamma handler e'lon qilinmagan.
MENU_ACTIONS: dict = {}


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
        _collect.get(user_id)["caption"] = text
        await message.reply_text(
            "📝 Izoh saqlandi. Chek qismlarini yuborishda davom eting.",
            reply_markup=COLLECT_MENU,
        )
        return

    usage_id = await check_quota(update, context, "matn")
    if usage_id is None:
        return

    await context.bot.send_chat_action(message.chat_id, ChatAction.TYPING)

    try:
        parsed = await ai.parse_message(text, today=reports.today())
    except Exception:
        log.exception("AI tahlilida xatolik")
        db.usage_cancel(usage_id)
        await message.reply_text("⚠️ AI bilan bog'lanishda xatolik. Birozdan keyin urinib ko'ring.")
        return

    db.usage_finish(usage_id, parsed.get("_usage"))
    niyat = parsed["niyat"]

    if niyat == "savol":
        # Savol alohida (qimmatroq) amal — o'z limiti va o'z hisobi bor.
        qa_id = await check_quota(update, context, "savol")
        if qa_id is None:
            return
        try:
            rows = db.rows_for_ai(user_id, config.QA_MAX_ROWS)
            answer, qa_usage = await ai.answer_question(text, rows, today=reports.today())
        except Exception:
            log.exception("AI javobida xatolik")
            db.usage_cancel(qa_id)
            await message.reply_text("⚠️ Javob tayyorlashda xatolik yuz berdi.")
            return
        if qa_usage:
            db.usage_finish(qa_id, qa_usage)
        else:
            db.usage_cancel(qa_id)  # yozuv yo'q edi, API chaqirilmadi
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
    user = update.effective_user
    user_id = user.id
    data = query.data or ""

    # Obuna tugmalari kirish chegarasidan OLDIN keladi — muddati tugagan
    # foydalanuvchi ham tarifni tanlay olishi kerak.
    if data.startswith(("sub:", "subok:", "subno:")):
        await on_subscription_callback(update, context)
        return

    # Boshqa hamma tugma uchun bot bilan bir xil kirish qoidasi.
    access = db.access_status(user_id, user.first_name or "", user.username)
    if not access["ok"]:
        await query.answer(
            "Obuna muddati tugagan." if access["status"] == "expired" else "Ruxsat yo'q.",
            show_alert=True,
        )
        return

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
        _collect.set(user_id, {"images": list(last["images"]), "caption": last["caption"]})
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


# --------------------------------------------------------------------------- #
# Obuna holati (hamma uchun) va admin buyruqlari (faqat ega uchun)
# --------------------------------------------------------------------------- #

def _fmt_dt(dt) -> str:
    return dt.strftime("%d.%m.%Y") if dt else "—"


# --------------------------------------------------------------------------- #
# Obuna tariflari
# --------------------------------------------------------------------------- #

def _fmt_price(amount: int) -> str:
    return f"{amount:,}".replace(",", " ") + " so'm"


def plans_keyboard() -> InlineKeyboardMarkup:
    rows = []
    for p in config.SUBSCRIPTION_PLANS:
        disc = config.plan_discount_percent(p)
        suffix = f" · −{disc}%" if disc else ""
        rows.append([
            InlineKeyboardButton(
                f"{p['label']} — {_fmt_price(p['price'])}{suffix}",
                callback_data=f"sub:{p['code']}",
            )
        ])
    return InlineKeyboardMarkup(rows)


def plans_text(access: dict | None = None) -> str:
    lines = ["💎 <b>Obuna tariflari</b>", ""]

    status = (access or {}).get("status")
    if status == "trial":
        lines += [
            f"🎁 Bepul sinovingiz faol — <b>{access['days_left']} kun</b> qoldi.",
            "<i>Hoziroq obuna bo'lsangiz, qolgan bepul kunlar yo'qolmaydi — "
            "obuna muddati ularning ustiga qo'shiladi.</i>",
            "",
        ]
    elif status == "subscribed":
        lines += [
            f"✅ Obunangiz faol — <b>{access['days_left']} kun</b> qoldi.",
            "<i>Uzaytirsangiz, yangi muddat mavjudining ustiga qo'shiladi.</i>",
            "",
        ]

    for p in config.SUBSCRIPTION_PLANS:
        disc = config.plan_discount_percent(p)
        per_month = config.plan_monthly_price(p)
        line = f"<b>{p['label']}</b> — {_fmt_price(p['price'])}"
        if disc:
            line += f"  <b>({disc}% tejash)</b>"
        lines.append(line)
        if p["months"] > 1:
            lines.append(f"    <i>oyiga {_fmt_price(per_month)}</i>")

    lines += [
        "",
        "<b>Obunada nima bor:</b>",
        "• Cheksiz matnli yozuv va chek o'qish",
        "• Grafik boshqaruv paneli",
        "• Savol-javob va barcha hisobotlar",
        "• CSV eksport",
        "",
        "Kerakli tarifni tanlang — so'rovingiz adminga yuboriladi.",
    ]
    return "\n".join(lines)


async def cmd_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tariflarni ko'rsatadi. ATAYLAB kirish chegarasidan tashqarida —
    muddati tugagan foydalanuvchi ham tarifni ko'ra olishi kerak."""
    user = update.effective_user
    if user is None:
        return
    access = db.access_status(user.id, user.first_name or "", user.username)

    if access["status"] == "owner":
        await update.effective_message.reply_text(
            "👑 Siz bot egasisiz — obuna kerak emas, cheksiz foydalanasiz.\n\n"
            + plans_text(),
            parse_mode=ParseMode.HTML,
        )
        return

    await update.effective_message.reply_text(
        plans_text(access), parse_mode=ParseMode.HTML, reply_markup=plans_keyboard()
    )


async def on_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tarif tanlash (foydalanuvchi) va tasdiqlash/rad etish (admin)."""
    query = update.callback_query
    user = update.effective_user
    data = query.data or ""

    # --- Foydalanuvchi tarif tanladi ---
    if data.startswith("sub:"):
        plan = config.plan_by_code(data[4:])
        if not plan:
            await query.answer("Tarif topilmadi", show_alert=True)
            return
        await query.answer("So'rov yuborildi ✅")
        await query.edit_message_text(
            f"📨 <b>So'rovingiz yuborildi</b>\n\n"
            f"Tarif: <b>{plan['label']}</b> — {_fmt_price(plan['price'])}\n\n"
            f"Admin tez orada bog'lanadi. To'lovdan so'ng obunangiz "
            f"avtomatik faollashadi.\n\n"
            f"Bevosita yozish: {reports.esc(_support_contact())}",
            parse_mode=ParseMode.HTML,
        )

        # Adminga bir bosishda tasdiqlash tugmasi bilan xabar.
        uname = f"@{user.username}" if user.username else "(username yo'q)"
        admin_text = (
            "🔔 <b>Yangi obuna so'rovi</b>\n\n"
            f"👤 {reports.esc(user.first_name or '')} {reports.esc(uname)}\n"
            f"🆔 <code>{user.id}</code>\n"
            f"💎 {plan['label']} — {_fmt_price(plan['price'])} ({plan['days']} kun)"
        )
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Tasdiqlash",
                                 callback_data=f"subok:{user.id}:{plan['code']}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"subno:{user.id}"),
        ]])
        for owner in config.OWNER_IDS:
            try:
                await context.bot.send_message(owner, admin_text,
                                               parse_mode=ParseMode.HTML, reply_markup=kb)
            except Exception:
                log.warning("Adminga so'rov yuborilmadi: %s", owner)
        return

    # --- Bundan keyingisi faqat admin uchun ---
    if user.id not in config.OWNER_IDS:
        await query.answer("Ruxsat yo'q.", show_alert=True)
        return

    if data.startswith("subok:"):
        _, raw_id, code = data.split(":")
        plan = config.plan_by_code(code)
        if not plan:
            await query.answer("Tarif topilmadi", show_alert=True)
            return
        target = int(raw_id)
        until = db.grant_subscription(target, plan["days"])
        await query.answer("Tasdiqlandi")
        await query.edit_message_text(
            f"✅ <b>Obuna berildi</b>\n\n"
            f"🆔 <code>{target}</code>\n"
            f"💎 {plan['label']} — {_fmt_price(plan['price'])}\n"
            f"📅 {_fmt_dt(until)} gacha",
            parse_mode=ParseMode.HTML,
        )
        try:
            await context.bot.send_message(
                target,
                f"🎉 <b>Obunangiz faollashtirildi!</b>\n\n"
                f"Tarif: {plan['label']}\n"
                f"Amal qilish muddati: <b>{_fmt_dt(until)}</b>\n\n"
                f"Rahmat! Holatni ko'rish: /holat",
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            log.info("Obuna xabarini yuborib bo'lmadi: %s", target)
        return

    if data.startswith("subno:"):
        target = int(data.split(":")[1])
        await query.answer("Rad etildi")
        await query.edit_message_text(f"❌ So'rov rad etildi (<code>{target}</code>).",
                                      parse_mode=ParseMode.HTML)
        return


@private_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    access = context.user_data.get("access") or db.access_status(user_id)

    if access["status"] == "owner":
        head = "👑 <b>Bot egasi</b> — cheksiz foydalanish"
    elif access["status"] == "subscribed":
        head = (f"✅ <b>Obuna faol</b>\n"
                f"Tugash sanasi: {_fmt_dt(access['until'])} "
                f"({access['days_left']} kun qoldi)")
    else:
        head = (f"🎁 <b>Bepul sinov</b>\n"
                f"Tugash sanasi: {_fmt_dt(access['until'])} "
                f"({access['days_left']} kun qoldi)")

    lines = [head, ""]

    if access["status"] != "owner":
        lines.append("<b>Bugungi limitlar:</b>")
        for op, (limit, label) in LIMITS.items():
            used = db.count_today(user_id, op)
            lines.append(f"  {label}: {used} / {limit}")
        lines.append("")

    n = len(db.all_rows(user_id))
    lines.append(f"📒 Bazangizda {n} ta yozuv bor.")

    # Ega bo'lmaganlarga tariflar shu yerdan ham ochiladi — sinov davri
    # faol bo'lsa ham obuna sotib olish mumkin.
    kb = None
    if access["status"] != "owner":
        lines += ["", "<i>Obunani hoziroq uzaytirsangiz, qolgan kunlar "
                      "yo'qolmaydi — ustiga qo'shiladi.</i>"]
        kb = plans_keyboard()

    await update.effective_message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=kb)


@owner_only
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    users = db.user_count()
    u30 = db.usage_summary(days=30)
    u1 = db.usage_summary(days=1)

    lines = [
        "🛠 <b>Admin paneli</b>", "",
        "<b>Foydalanuvchilar</b>",
        f"  Jami: {users['total']}",
        f"  Obunali: {users['subscribed']}",
        f"  Sinovda: {users['trial']}",
        f"  Bloklangan: {users['blocked']}",
        "",
        "<b>Xarajat (30 kun)</b>",
        f"  Chaqiruvlar: {u30['calls']}",
        f"  Narx: ${u30['cost_usd']:.2f}",
        f"  Keshdan o'qilgan: {u30['cache_read']:,} token".replace(",", " "),
    ]
    for op in u30["by_operation"]:
        lines.append(f"    {op['operation']}: {op['calls']} ta · ${op['cost_usd']:.2f}")
    lines += ["", f"<b>Bugun:</b> {u1['calls']} chaqiruv · ${u1['cost_usd']:.2f}"]

    top = db.top_spenders(days=30, limit=5)
    if top:
        lines += ["", "<b>Eng ko'p sarflaganlar (30 kun)</b>"]
        for t in top:
            who = reports.esc(t["first_name"] or str(t["user_id"]))
            uname = f" @{reports.esc(t['username'])}" if t["username"] else ""
            lines.append(f"  {who}{uname} — ${t['cost_usd']:.3f} ({t['calls']} ta)")

    lines += [
        "", "<b>Buyruqlar</b>",
        "<code>/berish 123456 30</code> — 30 kunlik obuna berish",
        "<code>/bloklash 123456</code> · <code>/ochish 123456</code>",
        "<code>/royxat</code> — oxirgi foydalanuvchilar",
    ]
    await update.effective_message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


@owner_only
async def cmd_grant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if len(args) < 2 or not args[0].isdigit() or not args[1].isdigit():
        await update.effective_message.reply_text("Foydalanish: /berish <user_id> <kun>")
        return
    target, days = int(args[0]), int(args[1])
    until = db.grant_subscription(target, days)
    await update.effective_message.reply_text(
        f"✅ {target} uchun obuna {_fmt_dt(until)} gacha uzaytirildi."
    )
    try:
        await context.bot.send_message(
            target,
            f"🎉 Obunangiz faollashtirildi!\nAmal qilish muddati: {_fmt_dt(until)}",
        )
    except Exception:
        log.info("Obuna xabarini yuborib bo'lmadi: %s", target)


@owner_only
async def cmd_block(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args or not args[0].isdigit():
        await update.effective_message.reply_text("Foydalanish: /bloklash <user_id>")
        return
    ok = db.set_blocked(int(args[0]), True)
    await update.effective_message.reply_text(
        f"🚫 {args[0]} bloklandi." if ok else "Foydalanuvchi topilmadi."
    )


@owner_only
async def cmd_unblock(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args or []
    if not args or not args[0].isdigit():
        await update.effective_message.reply_text("Foydalanish: /ochish <user_id>")
        return
    ok = db.set_blocked(int(args[0]), False)
    await update.effective_message.reply_text(
        f"✅ {args[0]} blokdan chiqarildi." if ok else "Foydalanuvchi topilmadi."
    )


@owner_only
async def cmd_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = db.list_users(30)
    if not rows:
        await update.effective_message.reply_text("Hozircha foydalanuvchi yo'q.")
        return
    lines = [f"👥 <b>Oxirgi {len(rows)} foydalanuvchi</b>", ""]
    for r in rows:
        st = db.access_status(r["user_id"])
        badge = {"owner": "👑", "subscribed": "✅", "trial": "🎁",
                 "expired": "⏳", "blocked": "🚫"}.get(st["status"], "•")
        uname = f" @{reports.esc(r['username'])}" if r["username"] else ""
        lines.append(
            f"{badge} <code>{r['user_id']}</code> {reports.esc(r['first_name'])}{uname}"
        )
    for chunk in _split_message("\n".join(lines)):
        await update.effective_message.reply_text(chunk, parse_mode=ParseMode.HTML)


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
    ("obuna", "Obuna tariflari"),
    ("holat", "Obuna holati va bugungi limitlar"),
]

# Faqat bot egasining «/» menyusida ko'rinadigan buyruqlar.
OWNER_COMMANDS = BOT_COMMANDS + [
    ("id", "Telegram ID'ingiz"),
    ("admin", "Statistika va sarf hisobi"),
    ("berish", "Obuna berish: /berish <id> <kun>"),
    ("bloklash", "Bloklash: /bloklash <id>"),
    ("ochish", "Blokdan chiqarish: /ochish <id>"),
    ("royxat", "Foydalanuvchilar ro'yxati"),
]


async def _post_init(app: Application) -> None:
    """Telegramdagi «/» menyusini to'ldiradi — buyruqlarni eslash shart emas."""
    from telegram import BotCommand, BotCommandScopeChat

    await app.bot.set_my_commands([BotCommand(c, d) for c, d in BOT_COMMANDS])

    # Egaga qo'shimcha buyruqlar ko'rinadi (/id va admin buyruqlari).
    owner_cmds = [BotCommand(c, d) for c, d in OWNER_COMMANDS]
    for owner in config.OWNER_IDS:
        try:
            await app.bot.set_my_commands(owner_cmds,
                                          scope=BotCommandScopeChat(chat_id=owner))
        except Exception as exc:
            log.warning("Ega buyruqlarini o'rnatib bo'lmadi (%s): %s", owner, exc)

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


def build_menu_actions() -> None:
    """Menyu tugmalarini handlerlarga bog'laydi. Barcha handlerlar e'lon
    qilingandan keyin chaqiriladi."""
    MENU_ACTIONS.update({
        "📊 Bugun": _period_command("bugun"),
        "📅 Hafta": _period_command("hafta"),
        "🗓 Oy": _period_command("oy"),
        "📈 Yil": _period_command("yil"),
        "🧾 Oxirgi": cmd_recent,
        "🤝 Qarzlar": cmd_debts,
        "📤 CSV": cmd_csv,
        "📖 Qo'llanma": cmd_guide,
        "💎 Obuna": cmd_plans,
        "🧾 Uzun chek": cmd_collect_start,
        "✅ Tayyor": cmd_collect_done,
        "❌ Bekor": cmd_collect_cancel,
    })


build_menu_actions()


def main() -> None:
    missing = config.missing_settings()
    if missing:
        raise SystemExit(
            ".env faylida quyidagilar yo'q: " + ", ".join(missing)
        )
    if not config.OWNER_IDS:
        log.warning(
            "OWNER_IDS bo'sh — admin buyruqlari hech kimga ishlamaydi. "
            "Botga /id yozib, ID'ingizni .env dagi OWNER_IDS ga qo'shing."
        )
    if config.ALLOWED_USER_IDS:
        log.info(
            "YOPIQ rejim: faqat %d ta ID kiritiladi. Hammaga ochish uchun "
            ".env dagi ALLOWED_USER_IDS ni bo'shating.", len(config.ALLOWED_USER_IDS)
        )
    else:
        log.info(
            "OCHIQ rejim: yangi foydalanuvchilar %d kunlik bepul sinov oladi.",
            config.TRIAL_DAYS,
        )

    db.init()

    app = (
        Application.builder()
        .token(config.TELEGRAM_TOKEN)
        .post_init(_post_init)
        # MUHIM (1000 foydalanuvchi uchun): standart holatda python-telegram-bot
        # yangilanishlarni BIRIN-KETIN qayta ishlaydi. AI chaqiruvi 2–16 soniya
        # davom etgani uchun bitta sekin chek butun navbatni to'xtatib qo'yardi.
        # concurrent_updates bilan foydalanuvchilar bir-birini kutmaydi.
        .concurrent_updates(config.MAX_CONCURRENT_UPDATES)
        .build()
    )

    app.add_handler(CommandHandler(["start", "yordam", "help"], cmd_start))
    app.add_handler(CommandHandler(["qollanma", "guide"], cmd_guide))
    app.add_handler(CommandHandler(["obuna", "tarif"], cmd_plans))
    app.add_handler(CommandHandler("holat", cmd_status))
    app.add_handler(CommandHandler("id", cmd_id))
    # Admin buyruqlari — owner_only dekoratori boshqalarga jimgina javob bermaydi.
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("berish", cmd_grant))
    app.add_handler(CommandHandler("bloklash", cmd_block))
    app.add_handler(CommandHandler("ochish", cmd_unblock))
    app.add_handler(CommandHandler("royxat", cmd_users))
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
