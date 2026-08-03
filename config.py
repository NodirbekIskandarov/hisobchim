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

# Yozuvlarni ajratish uchun arzon va tez model yetarli.
PARSE_MODEL = os.getenv("PARSE_MODEL", "claude-haiku-4-5-20251001").strip()
# Savollarga javob berish uchun kuchliroq model.
CHAT_MODEL = os.getenv("CHAT_MODEL", "claude-sonnet-5").strip()
# Chek rasmlarini o'qish uchun — eng aniq model. Arzonroq variant: claude-sonnet-5.
VISION_MODEL = os.getenv("VISION_MODEL", "claude-opus-5").strip()

DB_PATH = os.getenv("DB_PATH", "hisobchi.db")
CURRENCY = os.getenv("CURRENCY", "so'm")
TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Tashkent"))

# Faqat shu Telegram ID'lariga javob beradi. Bo'sh bo'lsa bot hech kimni kiritmaydi.
ALLOWED_USER_IDS = _ids("ALLOWED_USER_IDS")

# "obedga 50" -> 50 000 so'm deb tushunilsinmi?
SMALL_NUMBERS_ARE_THOUSANDS = _bool("SMALL_NUMBERS_ARE_THOUSANDS", True)

# Savolga javob berishda AI'ga beriladigan maksimal yozuvlar soni.
QA_MAX_ROWS = int(os.getenv("QA_MAX_ROWS", "500"))

# Bitta chek uchun maksimal rasm (uzun chekni bo'lib suratga olish uchun).
MAX_RECEIPT_PARTS = int(os.getenv("MAX_RECEIPT_PARTS", "8"))
# Bitta rasm uchun maksimal hajm (Anthropic API chegarasi ~5 MB).
MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", str(4_500_000)))

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
