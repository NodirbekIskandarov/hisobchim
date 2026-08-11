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
from urllib.parse import quote

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
import i18n
import rates
import reports
import sharecard

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


def lang_of(user_id: int, context: ContextTypes.DEFAULT_TYPE | None = None) -> str:
    """Foydalanuvchi tili. Bir so'rov ichida keshlanadi — har bir matn uchun
    bazaga borish shart emas."""
    if context is not None:
        cached = context.user_data.get("_lang")
        if cached:
            return cached
    value = i18n.normalize(db.get_lang(user_id))
    if context is not None:
        context.user_data["_lang"] = value
    return value


async def _deny(msg, user, access) -> None:
    """Kirishi yopiq foydalanuvchiga sababini tushuntiradi."""
    if msg is None:
        return
    lang = lang_of(user.id)
    if access["status"] == "blocked":
        await msg.reply_text(i18n.t(lang, "blocked"))
    elif access["status"] == "not_allowed":
        log.info("Yopiq rejim: id=%s username=%s", user.id, user.username)
        await msg.reply_text(i18n.t(lang, "closed_beta", id=user.id))
    else:  # expired
        await msg.reply_text(
            i18n.t(lang, "expired", contact=reports.esc(_support_contact())),
            parse_mode=ParseMode.HTML,
            reply_markup=plans_keyboard(lang),
        )


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

        await _deny(update.effective_message, user, access)
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

def main_menu(lang: str = "uz") -> ReplyKeyboardMarkup:
    """Har chaqiruvda quriladi — WEBAPP_URL ishga tushirilgandan keyin
    qo'shilsa, botni qayta ishga tushirmasdan ham tugma paydo bo'ladi."""
    rows = [
        ["today", "week", "month"],
        ["recent", "debts", "year"],
        ["longbill", "csv", "guide"],
        ["budget", "referral", "subs"],
    ]
    keyboard = [[KeyboardButton(i18n.btn(lang, key)) for key in row] for row in rows]
    if config.WEBAPP_URL:
        keyboard.append([
            KeyboardButton(
                i18n.btn(lang, "panel"), web_app=WebAppInfo(url=config.WEBAPP_URL)
            )
        ])
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        input_field_placeholder="Xarajat yozing yoki chek rasmini yuboring…",
    )

def collect_menu(lang: str = "uz") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[i18n.btn(lang, "ready"), i18n.btn(lang, "cancel")]],
        resize_keyboard=True,
        input_field_placeholder="…",
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


FIRST_STEPS = [
    ("obedga 45 ming", "Birinchi yozuv"),
    ("taksi 20k, kofe 25 ming", "Bitta xabarda ikkita"),
    ("oylik tushdi 8 mln", "Kirim yozish"),
]


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Birinchi tanishuv — qisqa. To'liq qo'llanma /qollanma da."""
    user = update.effective_user
    if user is None:
        return

    access = db.access_status(user.id, user.first_name or "", user.username)
    context.user_data["access"] = access

    # Taklif havolasi: /start ref12345
    payload = (context.args or [""])[0] if context.args else ""
    if payload:
        await _apply_referral(update, context, payload)
        access = db.access_status(user.id)

    if not access["ok"]:
        await _deny(update.effective_message, user, access)
        return

    lang = lang_of(user.id, context)
    is_new = len(db.all_rows(user.id)) == 0
    name = f", {reports.esc(user.first_name)}" if user.first_name else ""

    if is_new:
        # Yangi odamga uzun matn emas — bitta misol va bitta tugma.
        await update.effective_message.reply_text(
            i18n.t(lang, "welcome", name=name),
            parse_mode=ParseMode.HTML,
            reply_markup=main_menu(lang),
        )
        await update.effective_message.reply_text(
            i18n.t(lang, "try_prompt"),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton(f"«{example}»", callback_data=f"try:{i}")]
                 for i, (example, _) in enumerate(FIRST_STEPS)]
            ),
        )
        return

    text = _help_text()
    if access["status"] == "trial":
        text += (f"\n\n🎁 <b>Bepul sinov: {access['days_left']} kun qoldi.</b>\n"
                 "Tariflar: /obuna")
    elif access["status"] == "subscribed":
        text += f"\n\n✅ <b>Obuna faol</b> — {access['days_left']} kun qoldi."

    await update.effective_message.reply_text(
        text, parse_mode=ParseMode.HTML, reply_markup=main_menu(lang_of(update.effective_user.id, context))
    )


async def on_try_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Onboarding tugmasi — misolni haqiqiy yozuvga aylantiradi."""
    query = update.callback_query
    try:
        index = int((query.data or "try:0").split(":")[1])
        example = FIRST_STEPS[index][0]
    except (ValueError, IndexError):
        await query.answer("Misol topilmadi")
        return
    await query.answer(example)
    await query.edit_message_text(f"✍️ <i>{reports.esc(example)}</i>",
                                  parse_mode=ParseMode.HTML)
    # Xabarni foydalanuvchi o'zi yozgandek qayta ishlaymiz.
    await _process_text(update, context, example)


@private_only
async def cmd_guide(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(update.effective_user.id, context)
    for chunk in _split_message(i18n.cyr(lang, GUIDE_TEXT)):
        await update.effective_message.reply_text(
            chunk, parse_mode=ParseMode.HTML, reply_markup=main_menu(lang_of(update.effective_user.id, context))
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
        # Oy va yil hisobotini rasm qilib ulashsa bo'ladi — do'stlarga
        # ko'rsatiladigan natija botni o'zi reklama qiladi.
        markup = None
        if period in ("oy", "otgan_oy", "yil") and sharecard.available():
            markup = InlineKeyboardMarkup([[
                InlineKeyboardButton(
                    i18n.t(lang_of(update.effective_user.id, context), "share_btn"),
                    callback_data=f"share:{period}")
            ]])
        await update.effective_message.reply_text(
            text, parse_mode=ParseMode.HTML, reply_markup=markup)

    return handler


async def on_share_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Davr hisobotini PNG qilib yuboradi."""
    query = update.callback_query
    user_id = update.effective_user.id
    period = (query.data or "share:oy").split(":", 1)[1]

    await query.answer("🖼")
    start, end, label = reports.period_range(period)
    data = db.totals_unified(user_id, start, end)
    totals = data["totals"]
    currency = "som"
    cats = db.by_category_unified(user_id, start, end, config.KIND_CHIQIM)
    entries = len(db.list_range(user_id, start, end))

    me = await context.bot.get_me()
    png = await asyncio.to_thread(
        sharecard.build,
        title=label.capitalize(),
        kirim=totals.get(config.KIND_KIRIM, 0),
        chiqim=totals.get(config.KIND_CHIQIM, 0),
        categories=cats,
        currency=currency,
        entries=entries,
        bot_username=me.username or "",
    )
    if not png:
        await query.answer("Rasm tayyorlab bo'lmadi", show_alert=True)
        return

    data = io.BytesIO(png)
    data.name = "hisobot.png"
    await context.bot.send_photo(
        query.message.chat_id, data,
        caption=i18n.t(lang_of(user_id, context), "share_caption"))


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
    await _send_csv(update, context, update.effective_user.id)


async def _send_csv(update: Update, context: ContextTypes.DEFAULT_TYPE,
                    user_id: int) -> None:
    """CSV faylni yuboradi. /csv va hisobni o'chirishdan oldin ishlatiladi."""
    rows = db.all_rows(user_id)
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
# To'lov cheki kutilayotgan foydalanuvchilar: user_id -> so'rov ID.
# 2 soat — odam kartaga o'tkazib, chekni topib yuborishga yetadi.
_awaiting_proof = TTLStore(ttl_seconds=7200, max_items=500)
# Hisobni o'chirishni tasdiqlash kutilmoqda: user_id -> True (5 daqiqa)
_awaiting_erase = TTLStore(ttl_seconds=300, max_items=100)


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
    currency = data.get("valyuta") or "som"
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
            "currency": currency,
        }
        for item in data["mahsulotlar"]
    ])

    start, end, _ = reports.period_range("bugun")
    day_total = db.totals_unified(user_id, start, end)["totals"][config.KIND_CHIQIM]

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


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    if user is None or message is None:
        return
    user_id = user.id
    caption = message.caption or ""

    # To'lov cheki kirish chegarasidan OLDIN tekshiriladi: muddati tugagan
    # foydalanuvchi ham to'lovni tasdiqlay olishi kerak.
    if await handle_payment_proof(update, context):
        return

    # Limit _process_receipt ichida hisoblanadi — bu yerda faqat kirish.
    access = db.access_status(user_id, user.first_name or "", user.username)
    context.user_data["access"] = access
    if not access["ok"]:
        await _deny(message, user, access)
        return

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
            reply_markup=collect_menu(lang_of(update.effective_user.id, context)),
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
        reply_markup=collect_menu(lang_of(update.effective_user.id, context)),
    )


@private_only
async def cmd_collect_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bucket = _collect.pop(update.effective_user.id, None)
    if not bucket or not bucket["images"]:
        await update.effective_message.reply_text(
            "Hech qanday rasm yuborilmadi.", reply_markup=main_menu(lang_of(update.effective_user.id, context))
        )
        return
    await update.effective_message.reply_text(
        f"📥 {len(bucket['images'])} ta qism qabul qilindi.", reply_markup=main_menu(lang_of(update.effective_user.id, context))
    )
    await _process_receipt(update, context, bucket["images"], bucket["caption"])


@private_only
async def cmd_collect_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _collect.pop(update.effective_user.id, None)
    await update.effective_message.reply_text("Bekor qilindi.", reply_markup=main_menu(lang_of(update.effective_user.id, context)))


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

    await _process_text(update, context, text, message)


async def _process_text(update: Update, context: ContextTypes.DEFAULT_TYPE,
                        text: str, message=None) -> None:
    """Matnli yozuvni tahlil qilib saqlaydi.

    `message` — javob yoziladigan xabar. Onboarding tugmasidan
    chaqirilganda bu callback xabari bo'ladi.
    """
    message = message or update.effective_message
    user_id = update.effective_user.id

    # «Uzun chek» rejimida yozilgan matn — chek uchun izoh.
    if user_id in _collect:
        _collect.get(user_id)["caption"] = text
        await message.reply_text(
            "📝 Izoh saqlandi. Chek qismlarini yuborishda davom eting.",
            reply_markup=collect_menu(lang_of(update.effective_user.id, context)),
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
    day_total = db.totals_unified(user_id, start, end)["totals"][config.KIND_CHIQIM]
    if day_total:
        body += f"\n\n<i>Bugungi chiqim: {reports.fmt_money(day_total)}</i>"

    single_kind = parsed["yozuvlar"][0]["turi"] if len(saved_ids) == 1 else None
    await message.reply_text(
        body, parse_mode=ParseMode.HTML,
        reply_markup=entry_keyboard(saved_ids, single_kind),
    )

    # Byudjet oshdimi? Faqat shu yozuvga tegishli kategoriyalarni tekshiramiz.
    touched = {item["kategoriya"] for item in parsed["yozuvlar"]
               if item["turi"] == config.KIND_CHIQIM}
    if touched:
        await check_budget_alerts(context, user_id, touched)


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

    # Obuna va hisobni o'chirish tugmalari kirish chegarasidan OLDIN keladi —
    # muddati tugagan foydalanuvchi ham to'lov qila olishi va ma'lumotini
    # o'chira olishi kerak.
    if data.startswith(("sub:", "subok:", "subno:")):
        await on_subscription_callback(update, context)
        return
    if data.startswith("erase:"):
        await on_erase_callback(update, context)
        return
    if data.startswith("lang:"):
        await on_lang_callback(update, context)
        return

    # Boshqa hamma tugma uchun bot bilan bir xil kirish qoidasi.
    access = db.access_status(user_id, user.first_name or "", user.username)
    if not access["ok"]:
        await query.answer(
            "Obuna muddati tugagan." if access["status"] == "expired" else "Ruxsat yo'q.",
            show_alert=True,
        )
        return

    if data.startswith("rem:"):
        await on_reminder_callback(update, context)
        return
    if data.startswith("share:"):
        await on_share_callback(update, context)
        return
    if data.startswith("try:"):
        await on_try_callback(update, context)
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


def plans_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
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


def plans_text(access: dict | None = None, lang: str = "uz") -> str:
    lines = [i18n.t(lang, "plans_title"), ""]

    status = (access or {}).get("status")
    if status == "trial":
        lines += [i18n.t(lang, "plans_trial", days=access["days_left"]), ""]
    elif status == "subscribed":
        lines += [i18n.t(lang, "plans_active", days=access["days_left"]), ""]

    for p in config.SUBSCRIPTION_PLANS:
        disc = config.plan_discount_percent(p)
        line = f"<b>{p['label']}</b> — {_fmt_price(p['price'])}"
        if disc:
            line += "  <b>(" + i18n.t(lang, "plan_save", pct=disc) + ")</b>"
        lines.append(line)
        if p["months"] > 1:
            per = _fmt_price(config.plan_monthly_price(p))
            lines.append("    <i>" + i18n.t(lang, "plan_month_price", price=per) + "</i>")

    lines += ["", i18n.t(lang, "plans_includes"), "", i18n.t(lang, "plans_pick")]
    return "\n".join(lines)


async def cmd_plans(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tariflarni ko'rsatadi. ATAYLAB kirish chegarasidan tashqarida —
    muddati tugagan foydalanuvchi ham tarifni ko'ra olishi kerak."""
    user = update.effective_user
    if user is None:
        return
    access = db.access_status(user.id, user.first_name or "", user.username)
    lang = lang_of(user.id, context)

    if access["status"] == "owner":
        await update.effective_message.reply_text(
            i18n.t(lang, "owner_no_sub") + "\n\n" + plans_text(lang=lang),
            parse_mode=ParseMode.HTML,
        )
        return

    await update.effective_message.reply_text(
        plans_text(access, lang), parse_mode=ParseMode.HTML,
        reply_markup=plans_keyboard(lang)
    )


def payment_text(plan: dict, lang: str = "uz") -> str:
    """Karta rekvizitlari va to'lov yo'riqnomasi."""
    contact = reports.esc(_support_contact())
    price = _fmt_price(plan["price"])
    if not config.card_ready():
        return i18n.t(lang, "pay_no_card", plan=plan["label"], price=price,
                      contact=contact)
    bank = f"\n🏦 {reports.esc(config.CARD_BANK)}" if config.CARD_BANK else ""
    return (i18n.t(lang, "pay_title") + "\n\n"
            + i18n.t(lang, "pay_body", plan=plan["label"], price=price,
                     card=reports.esc(config.card_pretty()),
                     holder=reports.esc(config.CARD_HOLDER), bank=bank,
                     contact=contact))


async def on_subscription_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi tarif tanladi — karta rekvizitlari ko'rsatiladi.

    Tasdiqlash bot ichida emas, admin web panelda amalga oshiriladi.
    """
    query = update.callback_query
    user = update.effective_user
    data = query.data or ""

    lang = lang_of(user.id, context)

    if data == "sub:bekor":
        _awaiting_proof.pop(user.id, None)
        await query.answer("OK")
        await query.edit_message_text(i18n.t(lang, "pay_cancelled"))
        return

    if not data.startswith("sub:"):
        await query.answer("Bu tugma endi ishlamaydi. /obuna dan qayta boshlang.",
                           show_alert=True)
        return

    plan = config.plan_by_code(data[4:])
    if not plan:
        await query.answer("Tarif topilmadi", show_alert=True)
        return

    request_id = db.add_subscription_request(user.id, plan["code"], plan["price"])
    # Endi shu foydalanuvchidan keladigan rasm chek deb qabul qilinadi.
    _awaiting_proof.set(user.id, request_id)

    await query.answer("💳")
    await query.edit_message_text(
        payment_text(plan, lang),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(i18n.t(lang, "erase_btn_no"),
                                 callback_data="sub:bekor")
        ]]),
    )

    uname = f"@{user.username}" if user.username else "(username yo'q)"
    note = (
        "🔔 <b>Yangi obuna so'rovi</b>\n\n"
        f"👤 {reports.esc(user.first_name or '')} {reports.esc(uname)}\n"
        f"🆔 <code>{user.id}</code>\n"
        f"💎 {plan['label']} — {_fmt_price(plan['price'])}\n\n"
        f"<i>To'lov cheki kutilmoqda.</i>\n"
        f"{config.ADMIN_PANEL_URL or 'admin panel'}/sorovlar"
    )
    for owner in config.OWNER_IDS:
        try:
            await context.bot.send_message(owner, note, parse_mode=ParseMode.HTML,
                                           disable_web_page_preview=True)
        except Exception:
            log.warning("Adminga bildirishnoma yuborilmadi: %s", owner)


async def handle_payment_proof(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Kutilayotgan to'lov chekini qabul qiladi. Qabul qilinsa True qaytaradi.

    Kirish chegarasidan TASHQARIDA chaqiriladi — muddati tugagan
    foydalanuvchi ham to'lov chekini yubora olishi kerak.
    """
    user = update.effective_user
    message = update.effective_message
    request_id = _awaiting_proof.get(user.id)
    if request_id is None:
        return False

    # Chek rasm (skrinshot) yoki PDF ko'rinishida kelishi mumkin —
    # bank ilovalari ko'pincha PDF kvitansiya beradi.
    kind = "rasm"
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.document:
        doc = message.document
        mime = (doc.mime_type or "").lower()
        name = (doc.file_name or "").lower()
        if mime == PDF_TYPE or name.endswith(".pdf"):
            kind = "pdf"
        elif not mime.startswith("image/"):
            await message.reply_text(
                "⚠️ Chekni <b>rasm</b> (JPG/PNG) yoki <b>PDF</b> ko'rinishida "
                "yuboring.",
                parse_mode=ParseMode.HTML)
            return True
        file_id = doc.file_id
    else:
        return False

    req = db.get_request(request_id)
    if req is None or req["status"] not in ("kutilmoqda", "tekshiruvda"):
        _awaiting_proof.pop(user.id, None)
        await message.reply_text(i18n.t(lang_of(user.id, context), "proof_stale"))
        return True

    db.attach_payment_proof(request_id, file_id, kind)
    _awaiting_proof.pop(user.id, None)

    plan = config.plan_by_code(req["plan_code"])
    label = plan["label"] if plan else req["plan_code"]
    await message.reply_text(
        i18n.t(lang_of(user.id, context), "proof_received", plan=label,
               price=_fmt_price(req["price"])),
        parse_mode=ParseMode.HTML,
    )

    uname = f"@{user.username}" if user.username else "(username yo'q)"
    caption = (
        "💳 <b>To'lov cheki keldi</b>\n\n"
        f"👤 {reports.esc(user.first_name or '')} {reports.esc(uname)}\n"
        f"🆔 <code>{user.id}</code>\n"
        f"💎 {label} — {_fmt_price(req['price'])}\n\n"
        f"Tasdiqlash: {config.ADMIN_PANEL_URL or 'admin panel'}/sorovlar"
    )
    for owner in config.OWNER_IDS:
        try:
            if kind == "pdf":
                await context.bot.send_document(owner, file_id, caption=caption,
                                                parse_mode=ParseMode.HTML)
            else:
                await context.bot.send_photo(owner, file_id, caption=caption,
                                             parse_mode=ParseMode.HTML)
        except Exception:
            log.warning("Adminga chek yuborilmadi: %s", owner)
    return True


# --------------------------------------------------------------------------- #
# Ma'lumot huquqlari: maxfiylik va hisobni o'chirish
# --------------------------------------------------------------------------- #

PRIVACY_TEXT = """🔒 <b>MAXFIYLIK SIYOSATI</b>

<b>Qanday ma'lumot saqlanadi</b>
• Telegram ID, ismingiz va username
• Siz yozgan xarajat/kirim yozuvlari: summa, kategoriya, izoh, sana
• Qarz yozuvlarida siz ko'rsatgan shaxs ismi
• Obuna muddati va to'lov tarixi

<b>Chek rasmlari</b>
Chek suratini yuborsangiz, u <b>faqat o'qish uchun</b> Anthropic (AQSh)
serveriga yuboriladi. Rasm bizda ham, u yerda ham saqlanmaydi —
o'qilgandan keyin darhol o'chadi. Faqat undan chiqqan <b>matnli
yozuvlar</b> sizning bazangizda qoladi.

Yozgan matnlaringiz ham xuddi shu tarzda tahlil uchun yuboriladi.
Anthropic bu ma'lumotni modelni o'qitishga ishlatmaydi.

<b>Kim ko'ra oladi</b>
• Siz — bot va boshqaruv paneli orqali
• Texnik xizmat ko'rsatuvchi administrator — nosozlikni tuzatish uchun
• Boshqa foydalanuvchilar sizning ma'lumotingizni <b>hech qachon</b>
  ko'rmaydi. Har bir yozuv Telegram ID bo'yicha ajratilgan.

<b>Qayerda saqlanadi</b>
O'zbekistondan tashqaridagi ijaraga olingan serverda, kirish faqat
kalit orqali. Har kuni shifrlangan zaxira nusxa olinadi.

<b>Sizning huquqlaringiz</b>
• /csv — barcha ma'lumotingizni fayl qilib olish
• /ochirish — hisobni va butun tarixni butunlay o'chirish
  (darhol va qaytarib bo'lmaydigan tarzda)

<b>To'lov</b>
Karta ma'lumotlaringiz bizga kelmaydi. Siz o'zingiz o'tkazma qilasiz
va faqat chek skrinshotini yuborasiz.

Savol: {contact}"""


@private_only
async def cmd_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/kurs — bugungi kurs; /kurs 12800 — qo'lda o'rnatish."""
    msg = update.effective_message
    args = context.args or []
    today = reports.today()

    if args:
        value = _parse_amount_uz(args[0])
        # «12800» ni ming deb olib yubormaslik uchun: kurs har doim to'liq son.
        raw = "".join(ch for ch in args[0] if ch.isdigit() or ch == ".")
        try:
            value = float(raw)
        except ValueError:
            value = None
        if not value or not (1_000 <= value <= 1_000_000):
            await msg.reply_text(
                "Kursni to'liq yozing, masalan: <code>/kurs 12800</code>",
                parse_mode=ParseMode.HTML)
            return
        db.set_rate("usd", today, value, f"qolda:{update.effective_user.id}")
        rates.clear_cache()
        await msg.reply_text(
            f"✅ Bugungi kurs o'rnatildi: <b>1 $ = {reports.fmt_money(value)}</b>\n\n"
            f"<i>Bugundan keyingi yozuvlar shu kurs bilan hisoblanadi. "
            f"Ilgari kiritilgan yozuvlar o'z kunidagi kursda qoladi.</i>",
            parse_mode=ParseMode.HTML)
        return

    rate = await asyncio.to_thread(rates.get, "usd", today)
    source = db.rate_source("usd", today) or "avtomatik"
    manba = "Markaziy bank" if source.startswith("cbu") else (
        "qo'lda kiritilgan" if source.startswith("qolda") else source)
    await msg.reply_text(
        f"💱 <b>Valyuta kursi</b>\n\n"
        f"1 $ = <b>{reports.fmt_money(rate)}</b>\n"
        f"<i>Manba: {manba}</i>\n\n"
        f"Dollarda yozgan yozuvlaringiz shu kurs bilan umumiy hisobga "
        f"qo'shiladi. Har bir yozuv o'z kunidagi kursni saqlab qoladi — "
        f"kurs o'zgarsa ham eski hisobot o'zgarmaydi.\n\n"
        f"O'zgartirish: <code>/kurs 12800</code>",
        parse_mode=ParseMode.HTML)


async def job_refresh_rates(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Har kuni ertalab kursni yangilaydi — kun davomida tarmoqqa
    chiqmasdan ishlash uchun."""
    try:
        result = await asyncio.to_thread(rates.refresh)
        log.info("Kurslar yangilandi: %s", result)
    except Exception:
        log.warning("Kursni yangilab bo'lmadi", exc_info=True)


async def cmd_lang(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Interfeys tilini tanlash. Kirish chegarasidan tashqarida —
    muddati tugagan foydalanuvchi ham tilni o'zgartira olishi kerak."""
    user = update.effective_user
    if user is None:
        return
    db.get_or_create_user(user.id, user.first_name or "", user.username)
    lang = lang_of(user.id, context)
    await update.effective_message.reply_text(
        i18n.t(lang, "lang_choose"),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(label, callback_data=f"lang:{code}")]
            for code, label in i18n.LANGS.items()
        ]),
    )


async def on_lang_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    code = i18n.normalize((query.data or "lang:uz").split(":")[1])
    db.set_lang(user.id, code)
    context.user_data["_lang"] = code
    await query.answer(i18n.LANGS[code])
    await query.edit_message_text(i18n.t(code, "lang_set"))
    # Klaviatura yangi tilda qayta chiziladi.
    await context.bot.send_message(
        query.message.chat_id, i18n.btn(code, "guide") + " · /qollanma",
        reply_markup=main_menu(code))


async def cmd_privacy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maxfiylik siyosati — kirish chegarasidan tashqarida."""
    lang = lang_of(update.effective_user.id, context)
    await update.effective_message.reply_text(
        i18n.cyr(lang, PRIVACY_TEXT).format(contact=reports.esc(_support_contact())),
        parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def cmd_erase(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Hisobni o'chirish — ikki bosqichli tasdiqlash bilan."""
    user = update.effective_user
    if user is None:
        return
    rows = len(db.all_rows(user.id))
    lang = lang_of(user.id, context)
    _awaiting_erase.set(user.id, True)
    await update.effective_message.reply_text(
        i18n.t(lang, "erase_confirm", n=rows),
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(i18n.t(lang, "erase_btn_csv"),
                                  callback_data="erase:csv")],
            [InlineKeyboardButton(i18n.t(lang, "erase_btn_yes"),
                                  callback_data="erase:ha")],
            [InlineKeyboardButton(i18n.t(lang, "erase_btn_no"),
                                  callback_data="erase:yoq")],
        ]),
    )


async def on_erase_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    data = query.data or ""

    lang = lang_of(user.id, context)

    if data == "erase:yoq":
        _awaiting_erase.pop(user.id, None)
        await query.answer("OK")
        await query.edit_message_text(i18n.t(lang, "erase_cancelled"))
        return

    if data == "erase:csv":
        await query.answer("CSV")
        await _send_csv(update, context, user.id)
        await query.edit_message_text("📤 /ochirish")
        _awaiting_erase.pop(user.id, None)
        return

    if data == "erase:ha":
        if not _awaiting_erase.get(user.id):
            await query.answer(i18n.t(lang, "erase_expired"), show_alert=True)
            return
        _awaiting_erase.pop(user.id, None)
        stats = db.erase_user(user.id)
        await query.answer("🗑")
        await query.edit_message_text(
            i18n.t(lang, "erase_done", n=stats["transactions"]),
            parse_mode=ParseMode.HTML)
        log.info("Foydalanuvchi o'z hisobini o'chirdi: %s", user.id)
        return


# --------------------------------------------------------------------------- #
# Referal — do'st taklif qilish
# --------------------------------------------------------------------------- #

@private_only
async def cmd_referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    lang = lang_of(user.id, context)
    stats = db.referral_stats(user.id)
    me = await context.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref{user.id}"

    share = quote(i18n.t(lang, "referral_share_text"))
    share_url = f"https://t.me/share/url?url={quote(link)}&text={share}"

    await update.effective_message.reply_text(
        i18n.t(lang, "referral", bonus=config.REFERRAL_BONUS_DAYS, link=link,
               invited=stats["invited"], bonus_days=stats["bonus_days"]),
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton(i18n.t(lang, "referral_share_btn"), url=share_url)
        ]]),
    )


async def _apply_referral(update: Update, context: ContextTypes.DEFAULT_TYPE,
                          payload: str) -> None:
    """/start ref<id> — taklif qilganni qayd etadi va ikkalasiga bonus beradi."""
    user = update.effective_user
    if not payload.startswith("ref"):
        return
    raw = payload[3:]
    if not raw.isdigit():
        return
    referrer_id = int(raw)
    if not db.set_referrer(user.id, referrer_id):
        return

    bonus = config.REFERRAL_BONUS_DAYS
    db.add_bonus_days(user.id, bonus)
    db.add_bonus_days(referrer_id, bonus)
    log.info("Referal: %s -> %s (+%s kun)", referrer_id, user.id, bonus)

    await update.effective_message.reply_text(
        i18n.t(lang_of(user.id, context), "referral_welcome", bonus=bonus),
        parse_mode=ParseMode.HTML)
    try:
        await context.bot.send_message(
            referrer_id,
            i18n.t(lang_of(referrer_id), "referral_thanks",
                   name=reports.esc(user.first_name or "?"), bonus=bonus),
            parse_mode=ParseMode.HTML)
    except Exception:
        log.info("Referal xabari yuborilmadi: %s", referrer_id)


# --------------------------------------------------------------------------- #
# Byudjet
# --------------------------------------------------------------------------- #

_MULTIPLIERS = {
    "ming": 1_000, "k": 1_000, "минг": 1_000,
    "mln": 1_000_000, "million": 1_000_000, "mil": 1_000_000,
    "lim": 1_000_000, "m": 1_000_000, "млн": 1_000_000,
    "mlrd": 1_000_000_000, "milliard": 1_000_000_000,
}


def _parse_amount_uz(text: str) -> float | None:
    """«2 mln», «500 ming», «1 200 000», «20k» → son.

    AI'ga murojaat qilmaydi — byudjet buyrug'i tez va tekin bo'lishi kerak.
    """
    raw = (text or "").lower().replace(" ", " ").strip()
    if not raw:
        return None
    # Sonni va undan keyingi birlikni ajratamiz.
    number = ""
    rest = ""
    for i, ch in enumerate(raw):
        if ch.isdigit() or ch in ".,":
            number += "." if ch == "," else ch
        elif ch == " " and number and raw[i + 1:i + 2].isdigit():
            continue          # «1 200 000» ichidagi bo'sh joy
        elif number:
            rest = raw[i:].strip()
            break
    if not number:
        return None
    try:
        value = float(number)
    except ValueError:
        return None

    unit = rest.split()[0].strip(".") if rest else ""
    if unit in _MULTIPLIERS:
        return value * _MULTIPLIERS[unit]
    # Birliksiz kichik son ming deb olinadi — matn yozuvlaridagi qoida bilan bir xil.
    if config.SMALL_NUMBERS_ARE_THOUSANDS and value < 1000:
        return value * 1000
    return value


@private_only
async def cmd_budget(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/byudjet — ro'yxat; /byudjet <kategoriya> <summa> — o'rnatish."""
    user_id = update.effective_user.id
    args = context.args or []
    msg = update.effective_message

    if args:
        if args[-1].lower() in ("o'chir", "ochir", "0"):
            category = config.normalize_category(
                config.KIND_CHIQIM, " ".join(args[:-1]))
            ok = db.delete_budget(user_id, category)
            await msg.reply_text(
                f"🗑 «{category}» byudjeti o'chirildi." if ok
                else f"«{category}» uchun byudjet yo'q edi.")
            return

        amount = _parse_amount_uz(args[-1])
        category = config.normalize_category(config.KIND_CHIQIM, " ".join(args[:-1]))
        if not amount or amount <= 0:
            await msg.reply_text(
                "Summani tushunmadim.\n\n"
                "Masalan: <code>/byudjet oziq-ovqat 2 mln</code>",
                parse_mode=ParseMode.HTML)
            return
        db.set_budget(user_id, category, amount)
        await msg.reply_text(
            f"✅ <b>{category}</b> uchun oylik byudjet: "
            f"<b>{reports.fmt_money(amount, 'som')}</b>\n\n"
            f"80% va 100% ga yetganda ogohlantiraman.",
            parse_mode=ParseMode.HTML)
        return

    rows = db.budget_status(user_id)
    if not rows:
        cats = ", ".join(config.EXPENSE_CATEGORIES[:6])
        await msg.reply_text(
            "💰 <b>Oylik byudjet</b>\n\n"
            "Kategoriyaga oylik chegara qo'ying — oshib ketsa ogohlantiraman.\n\n"
            "<b>O'rnatish:</b>\n"
            "<code>/byudjet oziq-ovqat 2 mln</code>\n"
            "<code>/byudjet transport 500 ming</code>\n\n"
            "<b>O'chirish:</b>\n"
            "<code>/byudjet transport o'chir</code>\n\n"
            f"<i>Kategoriyalar: {cats} …</i>",
            parse_mode=ParseMode.HTML)
        return

    lines = ["💰 <b>Shu oylik byudjet</b>", ""]
    for r in rows:
        pct = r["percent"]
        bar_len = 10
        filled = min(bar_len, int(round(pct / 100 * bar_len)))
        bar = "█" * filled + "░" * (bar_len - filled)
        icon = "🔴" if pct >= 100 else ("🟡" if pct >= 80 else "🟢")
        lines.append(f"{icon} <b>{r['category']}</b>")
        lines.append(
            f"    {bar} {pct:.0f}%\n"
            f"    {reports.fmt_money(r['spent'], r['currency'])} / "
            f"{reports.fmt_money(r['limit'], r['currency'])}")
        if r["left"] >= 0:
            lines.append(f"    qoldi: {reports.fmt_money(r['left'], r['currency'])}")
        else:
            lines.append(f"    ⚠️ oshib ketdi: "
                         f"{reports.fmt_money(-r['left'], r['currency'])}")
        lines.append("")
    lines.append("<i>O'zgartirish: /byudjet &lt;kategoriya&gt; &lt;summa&gt;</i>")
    await msg.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def check_budget_alerts(context: ContextTypes.DEFAULT_TYPE, user_id: int,
                              categories: set[str]) -> None:
    """Yozuv qo'shilgandan keyin byudjet oshganini tekshiradi.

    Har daraja (80% va 100%) oyiga bir marta ogohlantiradi — aks holda
    har yozuvda xabar kelib bezdirardi.
    """
    month = datetime.now(config.TZ).strftime("%Y-%m")
    for r in db.budget_status(user_id):
        if r["category"] not in categories:
            continue
        level = 100 if r["percent"] >= 100 else (80 if r["percent"] >= 80 else 0)
        if not level:
            continue
        tag = f"{month}:{level}"
        already = r["notified"]
        if already == tag or (already.startswith(month) and
                              already.endswith(":100")):
            continue
        db.mark_budget_notified(user_id, r["category"], r["currency"], tag)
        if level == 100:
            text = (f"🔴 <b>{r['category']}</b> byudjeti oshib ketdi!\n\n"
                    f"Sarflandi: {reports.fmt_money(r['spent'], r['currency'])}\n"
                    f"Chegara: {reports.fmt_money(r['limit'], r['currency'])}\n"
                    f"Oshgan: {reports.fmt_money(-r['left'], r['currency'])}")
        else:
            text = (f"🟡 <b>{r['category']}</b> byudjetining "
                    f"{r['percent']:.0f}% i sarflandi.\n\n"
                    f"Qoldi: {reports.fmt_money(r['left'], r['currency'])}")
        try:
            await context.bot.send_message(user_id, text, parse_mode=ParseMode.HTML)
        except Exception:
            log.info("Byudjet ogohlantirishi yuborilmadi: %s", user_id)


# --------------------------------------------------------------------------- #
# Eslatma sozlamasi
# --------------------------------------------------------------------------- #

@private_only
async def cmd_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/eslatma 21 — har kuni soat 21:00 da; /eslatma o'chir — bekor."""
    user_id = update.effective_user.id
    args = context.args or []
    msg = update.effective_message

    lang = lang_of(user_id, context)

    if args:
        raw = args[0].lower()
        if raw in ("o'chir", "ochir", "yoq", "0", "выкл", "off"):
            db.set_reminder_hour(user_id, None)
            await msg.reply_text(i18n.t(lang, "reminder_off"))
            return
        digits = "".join(ch for ch in raw if ch.isdigit())
        if digits and 0 <= int(digits) <= 23:
            hour = int(digits)
            db.set_reminder_hour(user_id, hour)
            await msg.reply_text(i18n.t(lang, "reminder_on", hour=f"{hour:02d}"),
                                 parse_mode=ParseMode.HTML)
            return
        await msg.reply_text(i18n.t(lang, "reminder_bad_hour"))
        return

    current = db.get_reminder_hour(user_id)
    if current is None:
        await msg.reply_text(
            i18n.t(lang, "reminder_intro"),
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔔 20:00", callback_data="rem:20"),
                InlineKeyboardButton("🔔 21:00", callback_data="rem:21"),
                InlineKeyboardButton("🔔 22:00", callback_data="rem:22"),
            ]]))
    else:
        await msg.reply_text(i18n.t(lang, "reminder_on", hour=f"{current:02d}"),
                             parse_mode=ParseMode.HTML)


async def on_reminder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    hour = int((query.data or "rem:21").split(":")[1])
    db.set_reminder_hour(update.effective_user.id, hour)
    await query.answer("🔔")
    await query.edit_message_text(
        i18n.t(lang_of(update.effective_user.id, context), "reminder_on",
               hour=f"{hour:02d}"),
        parse_mode=ParseMode.HTML)


async def cmd_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Egaga admin panel havolasini beradi."""
    user = update.effective_user
    if user is None or user.id not in config.OWNER_IDS:
        return
    url = config.ADMIN_PANEL_URL
    if not url:
        await update.effective_message.reply_text(
            "ADMIN_PANEL_URL sozlanmagan (.env faylida).")
        return
    pending = db.pending_request_count()
    text = [f"🛠 <b>Admin boshqaruv paneli</b>\n\n{url}"]
    if pending:
        text.append(f"\n\n⏳ {pending} ta obuna so'rovi javob kutmoqda.")
    await update.effective_message.reply_text(
        "".join(text), parse_mode=ParseMode.HTML, disable_web_page_preview=True)


@private_only
async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    access = context.user_data.get("access") or db.access_status(user_id)

    lang = lang_of(user_id, context)

    if access["status"] == "owner":
        head = i18n.t(lang, "status_owner")
    elif access["status"] == "subscribed":
        head = i18n.t(lang, "status_sub", until=_fmt_dt(access["until"]),
                      days=access["days_left"])
    else:
        head = i18n.t(lang, "status_trial", until=_fmt_dt(access["until"]),
                      days=access["days_left"])

    lines = [head, ""]

    if access["status"] != "owner":
        lines.append(i18n.t(lang, "status_limits"))
        for op, (limit, label) in LIMITS.items():
            used = db.count_today(user_id, op)
            lines.append(f"  {label}: {used} / {limit}")
        lines.append("")

    n = len(db.all_rows(user_id))
    lines.append(i18n.t(lang, "status_rows", n=n))

    # Ega bo'lmaganlarga tariflar shu yerdan ham ochiladi — sinov davri
    # faol bo'lsa ham obuna sotib olish mumkin.
    kb = None
    if access["status"] != "owner":
        lines += ["", i18n.t(lang, "status_extend_hint")]
        kb = plans_keyboard(lang)

    await update.effective_message.reply_text(
        "\n".join(lines), parse_mode=ParseMode.HTML, reply_markup=kb)


# Admin boshqaruvi bot ichidan OLIB TASHLANDI — hammasi alohida web
# panelda: https://hisobchim.niskandarov.uz
# Sabab: statistikani, foydalanuvchilarni va to'lovlarni chat oynasida
# boshqarish noqulay va xatoga moyil edi.


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE):
    log.exception("Handler xatoligi", exc_info=context.error)


# --------------------------------------------------------------------------- #
# Rejalashtirilgan vazifalar
# --------------------------------------------------------------------------- #

async def job_daily_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Har soatda ishlaydi va shu soatga eslatma buyurganlarga xabar yuboradi."""
    hour = datetime.now(config.TZ).hour
    users = db.users_for_reminder(hour)
    if not users:
        return
    today = reports.today()
    sent = 0
    for user_id in users:
        try:
            lang = lang_of(user_id)
            s = db.day_summary(user_id, today)
            if s["count"]:
                parts = []
                for cur, amount in s["chiqim"].items():
                    parts.append("−" + reports.fmt_money(amount, cur))
                for cur, amount in s["kirim"].items():
                    parts.append("+" + reports.fmt_money(amount, cur))
                text = i18n.t(lang, "daily_summary", n=s["count"],
                              parts=" · ".join(parts))
            else:
                text = i18n.t(lang, "daily_empty")
            await context.bot.send_message(user_id, text, parse_mode=ParseMode.HTML)
            sent += 1
        except Exception:
            log.info("Eslatma yuborilmadi: %s", user_id)
        await asyncio.sleep(0.06)      # Telegram cheklovi
    log.info("Kunlik eslatma: %s ta yuborildi (soat %s)", sent, hour)


async def job_expiry_warning(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Muddati tugayotganlarni ogohlantiradi — konversiyaning asosiy manbai."""
    rows = db.users_expiring((3, 1))
    if not rows:
        return
    sent = 0
    for r in rows:
        user_id = r["user_id"]
        try:
            lang = lang_of(user_id)
            total = len(db.all_rows(user_id))
            if r["kind"] == "sinov":
                head = (i18n.t(lang, "expiry_trial", days=r["days_left"])
                        if r["days_left"] > 0
                        else i18n.t(lang, "expiry_trial_today"))
                body = i18n.t(lang, "expiry_trial_body", n=total)
            else:
                head = (i18n.t(lang, "expiry_sub", days=r["days_left"])
                        if r["days_left"] > 0
                        else i18n.t(lang, "expiry_sub_today"))
                body = i18n.t(lang, "expiry_sub_body")
            await context.bot.send_message(
                user_id, f"{head}\n\n{body}", parse_mode=ParseMode.HTML,
                reply_markup=plans_keyboard(lang))
            db.mark_warned(user_id, r["stage"])
            sent += 1
        except Exception:
            log.info("Ogohlantirish yuborilmadi: %s", user_id)
        await asyncio.sleep(0.06)
    log.info("Muddat ogohlantirishi: %s ta yuborildi", sent)


def schedule_jobs(app: Application) -> None:
    """Vaqtga bog'liq vazifalarni ro'yxatga oladi."""
    jq = app.job_queue
    if jq is None:
        log.warning("JobQueue yo'q — eslatmalar ishlamaydi. "
                    "pip install 'python-telegram-bot[job-queue]'")
        return
    # Har soatning boshida: o'sha soatga eslatma buyurganlarga.
    jq.run_custom(job_daily_reminder,
                  job_kwargs={"trigger": "cron", "minute": 0, "timezone": config.TZ},
                  name="kunlik-eslatma")
    # Har kuni 10:00 da: muddati tugayotganlarga.
    jq.run_custom(job_expiry_warning,
                  job_kwargs={"trigger": "cron", "hour": 10, "minute": 0,
                              "timezone": config.TZ},
                  name="muddat-ogohlantirishi")
    # Kursni ertalab yangilaymiz — kun davomida yozuvlar tarmoqqa
    # chiqmasdan, bazadagi kurs bilan hisoblanadi.
    jq.run_custom(job_refresh_rates,
                  job_kwargs={"trigger": "cron", "hour": 8, "minute": 5,
                              "timezone": config.TZ},
                  name="kurs-yangilash")
    jq.run_once(job_refresh_rates, when=5, name="kurs-boshlangich")
    log.info("Rejalashtirilgan vazifalar yoqildi: eslatma (har soat), "
             "muddat ogohlantirishi (10:00)")


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
    ("byudjet", "Oylik byudjet qo'yish"),
    ("eslatma", "Kunlik eslatmani sozlash"),
    ("kurs", "Dollar kursi"),
    ("taklif", "Do'st taklif qilib bepul kun olish"),
    ("til", "Til / Язык"),
    ("maxfiylik", "Maxfiylik siyosati"),
    ("ochirish", "Hisobni butunlay o'chirish"),
]

# Faqat bot egasining «/» menyusida ko'rinadigan buyruqlar.
# Admin boshqaruvi web panelga ko'chirildi — bu yerda faqat /panel qoldi.
OWNER_COMMANDS = BOT_COMMANDS + [
    ("id", "Telegram ID'ingiz"),
    ("panel", "Admin boshqaruv paneli"),
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
    handlers = {
        "today": _period_command("bugun"),
        "week": _period_command("hafta"),
        "month": _period_command("oy"),
        "year": _period_command("yil"),
        "recent": cmd_recent,
        "debts": cmd_debts,
        "csv": cmd_csv,
        "guide": cmd_guide,
        "subs": cmd_plans,
        "budget": cmd_budget,
        "referral": cmd_referral,
        "longbill": cmd_collect_start,
        "ready": cmd_collect_done,
        "cancel": cmd_collect_cancel,
    }
    # Ikkala tildagi tugma matni ham qabul qilinadi: foydalanuvchi tilni
    # almashtirsa, eski klaviatura hali ekranda turgan bo'lishi mumkin.
    for text, key in i18n.menu_lookup().items():
        if key in handlers:
            MENU_ACTIONS[text] = handlers[key]


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
    app.add_handler(CommandHandler("panel", cmd_panel))
    app.add_handler(CommandHandler(["til", "lang", "yazyk"], cmd_lang))
    app.add_handler(CommandHandler(["maxfiylik", "privacy"], cmd_privacy))
    app.add_handler(CommandHandler(["ochirish", "hisobniochir"], cmd_erase))
    app.add_handler(CommandHandler(["taklif", "referal"], cmd_referral))
    app.add_handler(CommandHandler(["byudjet", "budjet"], cmd_budget))
    app.add_handler(CommandHandler("eslatma", cmd_reminder))
    app.add_handler(CommandHandler(["kurs", "valyuta"], cmd_rate))
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
    schedule_jobs(app)

    log.info("Bot ishga tushdi. To'xtatish: Ctrl+C")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
