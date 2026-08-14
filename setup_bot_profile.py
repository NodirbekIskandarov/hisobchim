"""Bot profilini Telegram API orqali sozlaydi.

Nima o'rnatiladi (har biri o'zbek va rus tillari uchun alohida):
  setMyName              — bot nomi (64 belgigacha)
  setMyShortDescription  — chat ro'yxatida va qidiruvda (120 belgigacha)
  setMyDescription       — «Start» tugmasi ustidagi matn (512 belgigacha)
  setMyCommands          — «/» menyusidagi buyruqlar ro'yxati

Ishlatish:
    python setup_bot_profile.py --dry-run    # faqat ko'rsatadi, yubormaydi
    python setup_bot_profile.py              # haqiqatan o'rnatadi
    python setup_bot_profile.py --show       # Telegramdagi hozirgi holatni o'qiydi

Token .env faylidagi TELEGRAM_TOKEN dan olinadi. U hech qachon ekranga
chiqarilmaydi va logga yozilmaydi — xatolik matnida ham niqoblanadi.
"""

from __future__ import annotations

import sys

import httpx

import config

API = "https://api.telegram.org/bot{token}/{method}"

# Telegram til kodlari. Bo'sh satr — standart (til aniqlanmaganda ko'rinadi).
# Telegram o'zbek lotin/kirill ni ajratmaydi, ikkalasi ham "uz".
LANGS = ["", "uz", "ru"]

NAME = {
    "": "Tanga",
    "uz": "Tanga",
    "ru": "Tanga",
}

SHORT = {
    "": "Xarajatlaringizni oddiy tilda yozing — men hisoblab, hisobot "
        "qilib beraman. 7 kun bepul.",
    "uz": "Xarajatlaringizni oddiy tilda yozing — men hisoblab, hisobot "
          "qilib beraman. 7 kun bepul.",
    "ru": "Пишите расходы обычным текстом — я посчитаю и составлю отчёт. "
          "7 дней бесплатно.",
}

DESCRIPTION = {
    "": (
        "Xarajatlaringizni oddiy tilda yozing — qolganini men qilaman.\n\n"
        "«obedga 45 ming» deb yozsangiz kifoya: summani ajrataman, "
        "kategoriyaga qo'yaman va istalgan payt hisobot beraman.\n\n"
        "• Chek suratini yuborsangiz — har bir mahsulotni o'qib chiqaman\n"
        "• Kunlik, haftalik, oylik va yillik hisobot\n"
        "• Byudjet qo'ying — chegaraga yaqinlashganda ogohlantiraman\n"
        "• Qarz berdim/oldim — kimga qancha, esdan chiqmaydi\n"
        "• So'm va dollar bitta hisobda birlashadi\n\n"
        "Birinchi 7 kun bepul. Boshlash uchun «Start» bosing."
    ),
    "ru": (
        "Пишите расходы обычным текстом — остальное сделаю я.\n\n"
        "Достаточно написать «обед 45 тысяч»: выделю сумму, определю "
        "категорию и в любой момент покажу отчёт.\n\n"
        "• Пришлите фото чека — распознаю каждую позицию\n"
        "• Отчёты за день, неделю, месяц и год\n"
        "• Поставьте бюджет — предупрежу при приближении к лимиту\n"
        "• Долги: кому и сколько — ничего не забудется\n"
        "• Сумы и доллары объединяются в одном учёте\n\n"
        "Первые 7 дней бесплатно. Нажмите «Start», чтобы начать."
    ),
}
DESCRIPTION["uz"] = DESCRIPTION[""]

COMMANDS = {
    "": [
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
        ("shartlar", "Xizmat shartlari"),
        ("ochirish", "Hisobni butunlay o'chirish"),
    ],
    "ru": [
        ("start", "Начать и помощь"),
        ("qollanma", "Полная инструкция"),
        ("chek", "Отправить длинный чек по частям"),
        ("bugun", "Отчёт за сегодня"),
        ("kecha", "Отчёт за вчера"),
        ("hafta", "Отчёт за неделю"),
        ("oy", "Отчёт за месяц"),
        ("otganoy", "Отчёт за прошлый месяц"),
        ("yil", "Отчёт за год"),
        ("oxirgi", "Последние записи"),
        ("qarz", "Открытые долги"),
        ("ochir", "Удалить запись: /ochir 12"),
        ("yopdim", "Закрыть долг: /yopdim 12"),
        ("csv", "Выгрузить все записи файлом"),
        ("obuna", "Тарифы подписки"),
        ("holat", "Статус подписки и лимиты"),
        ("byudjet", "Установить месячный бюджет"),
        ("eslatma", "Настроить ежедневное напоминание"),
        ("kurs", "Курс доллара"),
        ("taklif", "Пригласить друга и получить бесплатные дни"),
        ("til", "Til / Язык"),
        ("maxfiylik", "Политика конфиденциальности"),
        ("shartlar", "Условия сервиса"),
        ("ochirish", "Полностью удалить аккаунт"),
    ],
}
COMMANDS["uz"] = COMMANDS[""]

LIMITS = {"name": 64, "short_description": 120, "description": 512}


def _mask(text: str, token: str) -> str:
    """Token xato matniga tushib qolsa — niqoblaymiz."""
    return text.replace(token, "<TOKEN>") if token else text


def call(client: httpx.Client, token: str, method: str, payload: dict) -> dict:
    r = client.post(API.format(token=token, method=method), json=payload, timeout=30)
    try:
        data = r.json()
    except ValueError:
        raise SystemExit(f"{method}: javob JSON emas (HTTP {r.status_code})")
    if not data.get("ok"):
        raise SystemExit(
            f"{method} XATO: {_mask(str(data.get('description', data)), token)}")
    return data["result"]


def check_lengths() -> list[str]:
    """Telegram chegaralarini oldindan tekshiradi — API xatosini kutmasdan."""
    problems = []
    for lang in LANGS:
        for field, table in (("name", NAME), ("short_description", SHORT),
                             ("description", DESCRIPTION)):
            value = table.get(lang, table[""])
            if len(value) > LIMITS[field]:
                problems.append(
                    f"{field} [{lang or 'standart'}]: {len(value)} belgi, "
                    f"chegara {LIMITS[field]}")
    return problems


def show(client: httpx.Client, token: str) -> None:
    print("Telegramdagi HOZIRGI holat:\n")
    me = call(client, token, "getMe", {})
    print(f"  bot        : @{me['username']}  (id {me['id']})")
    for lang in LANGS:
        p = {"language_code": lang} if lang else {}
        label = lang or "standart"
        name = call(client, token, "getMyName", p)["name"]
        short = call(client, token, "getMyShortDescription", p)["short_description"]
        desc = call(client, token, "getMyDescription", p)["description"]
        cmds = call(client, token, "getMyCommands", p)
        print(f"\n  [{label}]")
        print(f"    nom          : {name}")
        print(f"    qisqa tavsif : {short[:70]}{'…' if len(short) > 70 else ''}")
        print(f"    tavsif       : {desc[:70].replace(chr(10), ' ')}"
              f"{'…' if len(desc) > 70 else ''}")
        print(f"    buyruqlar    : {len(cmds)} ta")


def apply(client: httpx.Client, token: str, dry: bool) -> None:
    me = call(client, token, "getMe", {})
    print(f"Bot: @{me['username']}  (id {me['id']})\n")

    for lang in LANGS:
        label = lang or "standart"
        base = {"language_code": lang} if lang else {}
        name = NAME.get(lang, NAME[""])
        short = SHORT.get(lang, SHORT[""])
        desc = DESCRIPTION.get(lang, DESCRIPTION[""])
        cmds = COMMANDS.get(lang, COMMANDS[""])

        print(f"[{label}]")
        print(f"  setMyName             {len(name):>3} belgi  {name}")
        print(f"  setMyShortDescription {len(short):>3} belgi")
        print(f"  setMyDescription      {len(desc):>3} belgi")
        print(f"  setMyCommands         {len(cmds):>3} ta buyruq")

        if dry:
            print()
            continue

        call(client, token, "setMyName", {**base, "name": name})
        call(client, token, "setMyShortDescription",
             {**base, "short_description": short})
        call(client, token, "setMyDescription", {**base, "description": desc})
        call(client, token, "setMyCommands", {
            **base,
            "commands": [{"command": c, "description": d} for c, d in cmds],
        })
        print("  -> o'rnatildi\n")

    if dry:
        print("(--dry-run: hech narsa yuborilmadi)")


def main() -> None:
    token = config.TELEGRAM_TOKEN
    if not token:
        raise SystemExit(".env faylida TELEGRAM_TOKEN yo'q.")

    problems = check_lengths()
    if problems:
        print("Chegaradan oshgan matnlar:")
        for p in problems:
            print("  -", p)
        raise SystemExit(1)

    with httpx.Client() as client:
        if "--show" in sys.argv:
            show(client, token)
        else:
            apply(client, token, dry="--dry-run" in sys.argv)


if __name__ == "__main__":
    main()
