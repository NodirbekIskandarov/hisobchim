"""Sozlamalar. Barcha maxfiy qiymatlar .env faylidan o'qiladi."""

from __future__ import annotations

import os
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "ha", "on"}


def _ids(name: str) -> set[int]:
    raw = os.getenv(name, "")
    out: set[int] = set()
    for chunk in raw.replace(";", ",").split(","):
        chunk = chunk.strip()
        if chunk.lstrip("-").isdigit():
            out.add(int(chunk))
    return out


TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "").strip()
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()

# Grafik boshqaruv paneli (Telegram Mini App) manzili. Bo'sh bo'lsa
# tegishli tugma ko'rsatilmaydi — webapp.py alohida joylashtirilishi kerak,
# HTTPS bilan (Telegram Mini App talabi).
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()

# Yozuvlarni ajratish uchun arzon va tez model yetarli.
PARSE_MODEL = os.getenv("PARSE_MODEL", "claude-haiku-4-5-20251001").strip()
# Savollarga javob berish uchun kuchliroq model.
CHAT_MODEL = os.getenv("CHAT_MODEL", "claude-sonnet-5").strip()
# Chek rasmlarini o'qish uchun — eng aniq model. Arzonroq variant: claude-sonnet-5.
VISION_MODEL = os.getenv("VISION_MODEL", "claude-opus-5").strip()

# Model narxlari ($ / 1M token): (kirish, chiqish). Keshdan o'qish kirish
# narxining ~0.1 barobari, keshga yozish ~1.25 barobari (5 daqiqalik TTL).
# Narxlar o'zgarsa shu yerdan yangilanadi — hisob-kitob avtomatik moslashadi.
MODEL_PRICES = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-haiku-4-5": (1.00, 5.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-opus-5": (5.00, 25.00),
    "claude-opus-4-8": (5.00, 25.00),
}
CACHE_READ_MULTIPLIER = 0.10
CACHE_WRITE_MULTIPLIER = 1.25


def cost_usd(model: str, input_tokens: int, output_tokens: int,
             cache_read: int = 0, cache_write: int = 0) -> float:
    """Bitta API chaqiruvining narxi. Noma'lum model uchun 0 qaytaradi —
    hisob past ko'rsatilishi jimgina xato ko'rsatishdan yaxshiroq emas,
    shuning uchun noma'lum model loglarda ko'rinadi."""
    price = MODEL_PRICES.get(model)
    if not price:
        return 0.0
    pin, pout = price
    return (
        input_tokens / 1e6 * pin
        + output_tokens / 1e6 * pout
        + cache_read / 1e6 * pin * CACHE_READ_MULTIPLIER
        + cache_write / 1e6 * pin * CACHE_WRITE_MULTIPLIER
    )


DB_PATH = os.getenv("DB_PATH", "hisobchi.db")
CURRENCY = os.getenv("CURRENCY", "so'm")
TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Tashkent"))

# Qo'llab-quvvatlanadigan valyutalar. Har bir yozuv o'z valyutasida saqlanadi
# va hisobotlarda ALOHIDA ko'rsatiladi — kurs orqali birlashtirilmaydi
# (kurs vaqt bilan o'zgaradi, taxminiy konvertatsiya chalkashlik keltirib chiqaradi).
CURRENCY_SOM = "som"
CURRENCY_USD = "usd"
SUPPORTED_CURRENCIES = [CURRENCY_SOM, CURRENCY_USD]
CURRENCY_SYMBOLS = {CURRENCY_SOM: CURRENCY, CURRENCY_USD: "$"}


def normalize_currency(value: str | None) -> str:
    v = (value or "").strip().lower()
    return v if v in SUPPORTED_CURRENCIES else CURRENCY_SOM

# --------------------------------------------------------------------------- #
# Kirish huquqi
# --------------------------------------------------------------------------- #

# Bot egalari — obunasiz, limitsiz, cheksiz foydalanadi va admin buyruqlariga
# ega. Bo'sh bo'lsa hech kim admin emas.
OWNER_IDS = _ids("OWNER_IDS")

# Eskirgan: yopiq rejim uchun oq ro'yxat. Bo'sh bo'lsa bot HAMMAGA ochiq
# (obuna/sinov muddati bo'yicha tekshiriladi). To'ldirilgan bo'lsa faqat shu
# ID'lar kiradi — yopiq sinovdan o'tkazish uchun qulay.
ALLOWED_USER_IDS = _ids("ALLOWED_USER_IDS")

# Yangi foydalanuvchi uchun bepul sinov muddati (kun).
TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "7"))

# Obuna bo'lish uchun murojaat manzili (masalan @username).
SUPPORT_CONTACT = os.getenv("SUPPORT_CONTACT", "").strip()

# Admin web paneli manzili — egaga bildirishnomada ko'rsatiladi.
ADMIN_PANEL_URL = os.getenv("ADMIN_PANEL_URL", "").strip().rstrip("/")

# --------------------------------------------------------------------------- #
# Obuna tariflari
#
# Narxni o'zgartirish uchun shu ro'yxatni tahrirlang — bot matnlari, tejash
# foizi va oylik narx avtomatik qayta hisoblanadi.
# Uzoq muddatli obuna ataylab arzonroq: AI xarajati past, shuning uchun
# obunachini uzoq muddatga "qulflash" foydali.
# --------------------------------------------------------------------------- #

SUBSCRIPTION_PLANS = [
    {"code": "1m",  "days": 30,  "months": 1,  "price": 37_000,  "label": "Oylik"},
    {"code": "3m",  "days": 90,  "months": 3,  "price": 99_000,  "label": "3 oylik"},
    {"code": "6m",  "days": 180, "months": 6,  "price": 179_000, "label": "6 oylik"},
    {"code": "12m", "days": 365, "months": 12, "price": 289_000, "label": "Yillik"},
]


def plan_by_code(code: str) -> dict | None:
    return next((p for p in SUBSCRIPTION_PLANS if p["code"] == code), None)


def plan_monthly_price(plan: dict) -> int:
    return round(plan["price"] / plan["months"])


def plan_discount_percent(plan: dict) -> int:
    """Oylik tarifga nisbatan necha foiz tejaladi."""
    base = SUBSCRIPTION_PLANS[0]["price"] * plan["months"]
    if base <= 0 or plan["price"] >= base:
        return 0
    return round((base - plan["price"]) / base * 100)

# --------------------------------------------------------------------------- #
# Kunlik limitlar — suiiste'moldan himoya. Egalarga qo'llanmaydi.
# Bitta foydalanuvchi cheksiz so'rov yuborib katta xarajat keltirmasligi uchun.
# --------------------------------------------------------------------------- #
LIMIT_TEXT_PER_DAY = int(os.getenv("LIMIT_TEXT_PER_DAY", "120"))
LIMIT_RECEIPT_PER_DAY = int(os.getenv("LIMIT_RECEIPT_PER_DAY", "25"))
LIMIT_QA_PER_DAY = int(os.getenv("LIMIT_QA_PER_DAY", "30"))

# Bir vaqtda qayta ishlanadigan yangilanishlar soni. AI chaqiruvi sekin
# bo'lgani uchun foydalanuvchilar bir-birini kutmasligi kerak.
MAX_CONCURRENT_UPDATES = int(os.getenv("MAX_CONCURRENT_UPDATES", "64"))

# "obedga 50" -> 50 000 so'm deb tushunilsinmi?
SMALL_NUMBERS_ARE_THOUSANDS = _bool("SMALL_NUMBERS_ARE_THOUSANDS", True)

# Savolga javob berishda AI'ga beriladigan maksimal XOM yozuvlar soni.
# 500 da bitta savol ~42 000 token = ~$0.14 turardi. Jamlanmalar (kategoriya,
# kun va tur bo'yicha jamilar) baribir Python'da aniq hisoblanib alohida
# yuboriladi, shuning uchun modelga barcha xom yozuvlar kerak emas —
# 150 da narx ~$0.05 ga tushadi, javob sifati esa saqlanadi.
QA_MAX_ROWS = int(os.getenv("QA_MAX_ROWS", "150"))

# Bitta chek uchun maksimal rasm (uzun chekni bo'lib suratga olish uchun).
MAX_RECEIPT_PARTS = int(os.getenv("MAX_RECEIPT_PARTS", "8"))
# Bitta rasm uchun maksimal hajm (Anthropic API chegarasi ~5 MB).
MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", str(4_500_000)))
# Bitta PDF uchun maksimal hajm. Telegram botlar 20 MB gacha yuklab oladi,
# base64 esa hajmni ~33% oshiradi (API so'rovi chegarasi 32 MB).
MAX_PDF_BYTES = int(os.getenv("MAX_PDF_BYTES", str(15_000_000)))

KIND_CHIQIM = "chiqim"
KIND_KIRIM = "kirim"
KIND_QARZ_BERDIM = "qarz_berdim"   # men birovga qarz berdim
KIND_QARZ_OLDIM = "qarz_oldim"     # men birovdan qarz oldim

KINDS = [KIND_CHIQIM, KIND_KIRIM, KIND_QARZ_BERDIM, KIND_QARZ_OLDIM]
DEBT_KINDS = [KIND_QARZ_BERDIM, KIND_QARZ_OLDIM]

KIND_LABELS = {
    KIND_CHIQIM: "Chiqim",
    KIND_KIRIM: "Kirim",
    KIND_QARZ_BERDIM: "Qarz berdim",
    KIND_QARZ_OLDIM: "Qarz oldim",
}

KIND_ICONS = {
    KIND_CHIQIM: "🔻",
    KIND_KIRIM: "🔺",
    KIND_QARZ_BERDIM: "📤",
    KIND_QARZ_OLDIM: "📥",
}

EXPENSE_CATEGORIES = [
    "oziq-ovqat",
    "kafe va restoran",
    "transport",
    "uy-joy",
    "kommunal",
    "aloqa va internet",
    "salomatlik",
    "kiyim-kechak",
    "ta'lim",
    "dam olish",
    "sovg'a",
    "xizmatlar",
    "biznes xarajat",
    "boshqa chiqim",
]

INCOME_CATEGORIES = [
    "oylik",
    "biznes daromadi",
    "qo'shimcha ish",
    "sotuvdan",
    "sovg'a olindi",
    "investitsiya",
    "boshqa kirim",
]

DEBT_CATEGORIES = ["qarz"]

ALL_CATEGORIES = EXPENSE_CATEGORIES + INCOME_CATEGORIES + DEBT_CATEGORIES

CATEGORY_ICONS = {
    "oziq-ovqat": "🥦",
    "kafe va restoran": "🍽",
    "transport": "🚕",
    "uy-joy": "🏠",
    "kommunal": "💡",
    "aloqa va internet": "📶",
    "salomatlik": "💊",
    "kiyim-kechak": "👕",
    "ta'lim": "📚",
    "dam olish": "🎬",
    "sovg'a": "🎁",
    "xizmatlar": "🛠",
    "biznes xarajat": "💼",
    "boshqa chiqim": "📦",
    "oylik": "💰",
    "biznes daromadi": "📈",
    "qo'shimcha ish": "🧰",
    "sotuvdan": "🏷",
    "sovg'a olindi": "🎀",
    "investitsiya": "🪙",
    "boshqa kirim": "📥",
    "qarz": "🤝",
}


def fallback_category(kind: str) -> str:
    if kind == KIND_KIRIM:
        return "boshqa kirim"
    if kind in DEBT_KINDS:
        return "qarz"
    return "boshqa chiqim"


def normalize_category(kind: str, category: str | None) -> str:
    """AI qaytargan kategoriyani tekshiradi va turiga mos kelmasa tuzatadi."""
    cat = (category or "").strip().lower()
    if kind in DEBT_KINDS:
        return "qarz"
    if kind == KIND_KIRIM:
        return cat if cat in INCOME_CATEGORIES else "boshqa kirim"
    return cat if cat in EXPENSE_CATEGORIES else "boshqa chiqim"


def categories_for(kind: str) -> list[str]:
    if kind == KIND_KIRIM:
        return INCOME_CATEGORIES
    if kind in DEBT_KINDS:
        return DEBT_CATEGORIES
    return EXPENSE_CATEGORIES


def missing_settings() -> list[str]:
    missing = []
    if not TELEGRAM_TOKEN:
        missing.append("TELEGRAM_TOKEN")
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    return missing
