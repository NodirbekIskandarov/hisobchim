"""Ikki tilli interfeys: o'zbek (uz) va rus (ru).

Matnlar shu yerda — kodning ichida emas. Yangi til qo'shish uchun
har bir kalitga uchinchi qiymat qo'shilsa yetadi.

Kalit topilmasa o'zbekchasi qaytariladi, ya'ni tarjima yetishmasa ham
bot ishlaydi. Uzun qo'llanma (/qollanma) hozircha faqat o'zbekcha.
"""

from __future__ import annotations

import translit

# uzc — o'zbek kirill. Uning matnlari alohida yozilmaydi: lotinchasidan
# avtomatik o'giriladi (translit.py), shunda matn o'zgarganda ikkala
# yozuv ham birdan yangilanadi.
LANGS = {
    "uz": "🇺🇿 O'zbekcha (lotin)",
    "uzc": "🇺🇿 Ўзбекча (кирилл)",
    "ru": "🇷🇺 Русский",
}
DEFAULT = "uz"


def normalize(lang: str | None) -> str:
    lang = (lang or "").lower().strip().replace("-", "").replace("_", "")
    if lang in ("uzcyrl", "cyr", "kirill"):
        lang = "uzc"
    return lang if lang in LANGS else DEFAULT


# --------------------------------------------------------------------------- #
# Tugmalar. Menyu matn sifatida keladi, shuning uchun ikkala tilning
# tugmalari ham handlerga bog'lanadi (pastdagi menu_lookup).
# --------------------------------------------------------------------------- #

BUTTONS = {
    "today":    {"uz": "📊 Bugun",       "ru": "📊 Сегодня"},
    "week":     {"uz": "📅 Hafta",       "ru": "📅 Неделя"},
    "month":    {"uz": "🗓 Oy",          "ru": "🗓 Месяц"},
    "year":     {"uz": "📈 Yil",         "ru": "📈 Год"},
    "recent":   {"uz": "🧾 Oxirgi",      "ru": "🧾 Последние"},
    "debts":    {"uz": "🤝 Qarzlar",     "ru": "🤝 Долги"},
    "longbill": {"uz": "🧾 Uzun chek",   "ru": "🧾 Длинный чек"},
    "csv":      {"uz": "📤 CSV",         "ru": "📤 CSV"},
    "guide":    {"uz": "📖 Qo'llanma",   "ru": "📖 Инструкция"},
    "budget":   {"uz": "💰 Byudjet",     "ru": "💰 Бюджет"},
    "referral": {"uz": "🎁 Taklif",      "ru": "🎁 Пригласить"},
    "subs":     {"uz": "💎 Obuna",       "ru": "💎 Подписка"},
    "panel":    {"uz": "📊 Boshqaruv paneli", "ru": "📊 Панель управления"},
    "ready":    {"uz": "✅ Tayyor",      "ru": "✅ Готово"},
    "cancel":   {"uz": "❌ Bekor",       "ru": "❌ Отмена"},
}


T = {
    # ---- Kirish va umumiy ----
    "welcome": {
        "uz": ("👋 <b>Salom{name}!</b>\n\n"
               "Men sizning shaxsiy hisobchingizman. Xarajatlaringizni yozib "
               "boraman, kategoriyalarga ajrataman va hisobot beraman.\n\n"
               "<b>Boshlash juda oddiy — shunchaki menga yozing:</b>\n\n"
               "<code>obedga 45 ming</code>\n\n"
               "Tugmani bosib sinab ko'ring 👇"),
        "ru": ("👋 <b>Здравствуйте{name}!</b>\n\n"
               "Я ваш личный бухгалтер. Записываю расходы, распределяю их по "
               "категориям и составляю отчёты.\n\n"
               "<b>Начать просто — напишите мне:</b>\n\n"
               "<code>обед 45 тысяч</code>\n\n"
               "Нажмите кнопку, чтобы попробовать 👇"),
    },
    "try_prompt": {
        "uz": "Quyidagilardan birini bosing yoki o'zingiz yozing:",
        "ru": "Нажмите один из примеров или напишите свой:",
    },
    "blocked": {
        "uz": "🚫 Hisobingiz bloklangan.",
        "ru": "🚫 Ваш аккаунт заблокирован.",
    },
    "closed_beta": {
        "uz": "Bot hozircha yopiq sinovda.\nSizning ID: {id}",
        "ru": "Бот пока в закрытом тестировании.\nВаш ID: {id}",
    },
    "expired": {
        "uz": ("⏳ <b>Bepul muddat tugadi</b>\n\n"
               "Botdan foydalanishni davom ettirish uchun obuna kerak.\n"
               "Quyidagi tariflardan birini tanlang yoki <b>{contact}</b> ga yozing.\n\n"
               "<i>Ma'lumotlaringiz saqlanib turibdi — obunadan keyin hammasi "
               "joyida bo'ladi.</i>"),
        "ru": ("⏳ <b>Бесплатный период закончился</b>\n\n"
               "Чтобы продолжить пользоваться ботом, нужна подписка.\n"
               "Выберите тариф ниже или напишите <b>{contact}</b>.\n\n"
               "<i>Ваши данные сохранены — после оплаты всё будет на месте.</i>"),
    },
    "limit_reached": {
        "uz": ("⛔ Bugungi {label} chegarasi tugadi ({limit} ta).\n"
               "Ertaga yangilanadi."),
        "ru": ("⛔ Дневной лимит исчерпан: {label} ({limit}).\n"
               "Обновится завтра."),
    },
    "ai_error": {
        "uz": "⚠️ AI bilan bog'lanishda xatolik. Birozdan keyin urinib ko'ring.",
        "ru": "⚠️ Ошибка связи с AI. Попробуйте чуть позже.",
    },
    "not_understood": {
        "uz": "Tushunmadim. Summani aniq yozing, masalan: <code>obedga 45 ming</code>",
        "ru": "Не понял. Укажите сумму, например: <code>обед 45 тысяч</code>",
    },

    # ---- Til ----
    "lang_choose": {
        "uz": "🌐 <b>Til</b>\n\nInterfeys tilini tanlang:",
        "ru": "🌐 <b>Язык</b>\n\nВыберите язык интерфейса:",
    },
    "lang_set": {
        "uz": "✅ Til o'zbekchaga o'zgartirildi.",
        "ru": "✅ Язык изменён на русский.",
    },

    # ---- Obuna va to'lov ----
    "plans_title": {"uz": "💎 <b>Obuna tariflari</b>", "ru": "💎 <b>Тарифы подписки</b>"},
    "plans_trial": {
        "uz": ("🎁 Bepul sinovingiz faol — <b>{days} kun</b> qoldi.\n"
               "<i>Hoziroq obuna bo'lsangiz, qolgan bepul kunlar yo'qolmaydi — "
               "obuna muddati ularning ustiga qo'shiladi.</i>"),
        "ru": ("🎁 Пробный период активен — осталось <b>{days} дн.</b>\n"
               "<i>Если оформите подписку сейчас, оставшиеся бесплатные дни не "
               "пропадут — срок подписки добавится к ним.</i>"),
    },
    "plans_active": {
        "uz": ("✅ Obunangiz faol — <b>{days} kun</b> qoldi.\n"
               "<i>Uzaytirsangiz, yangi muddat mavjudining ustiga qo'shiladi.</i>"),
        "ru": ("✅ Подписка активна — осталось <b>{days} дн.</b>\n"
               "<i>При продлении новый срок добавится к текущему.</i>"),
    },
    "plans_includes": {
        "uz": ("<b>Obunada nima bor:</b>\n"
               "• Cheksiz matnli yozuv va chek o'qish\n"
               "• Grafik boshqaruv paneli\n"
               "• Savol-javob va barcha hisobotlar\n"
               "• Byudjet va kunlik eslatma\n"
               "• CSV eksport"),
        "ru": ("<b>Что входит в подписку:</b>\n"
               "• Неограниченные записи и распознавание чеков\n"
               "• Графическая панель управления\n"
               "• Вопросы-ответы и все отчёты\n"
               "• Бюджеты и ежедневные напоминания\n"
               "• Экспорт в CSV"),
    },
    "plans_pick": {
        "uz": "Kerakli tarifni tanlang — keyin to'lov rekvizitlari ko'rsatiladi.",
        "ru": "Выберите тариф — после этого появятся реквизиты для оплаты.",
    },
    "plan_month_price": {"uz": "oyiga {price}", "ru": "{price} в месяц"},
    "plan_save": {"uz": "{pct}% tejash", "ru": "экономия {pct}%"},
    "owner_no_sub": {
        "uz": "👑 Siz bot egasisiz — obuna kerak emas, cheksiz foydalanasiz.",
        "ru": "👑 Вы владелец бота — подписка не нужна, доступ без ограничений.",
    },

    "pay_title": {"uz": "💳 <b>To'lov</b>", "ru": "💳 <b>Оплата</b>"},
    "pay_body": {
        "uz": ("Tarif: <b>{plan}</b>\n"
               "To'lov summasi: <b>{price}</b>\n\n"
               "━━━━━━━━━━━━━━━━━━\n"
               "<b>Karta raqami</b>\n"
               "<code>{card}</code>\n"
               "👤 {holder}{bank}\n"
               "━━━━━━━━━━━━━━━━━━\n\n"
               "<b>Keyingi qadam:</b>\n"
               "1️⃣ Yuqoridagi kartaga <b>{price}</b> o'tkazing\n"
               "2️⃣ To'lov chekining <b>skrinshotini shu yerga yuboring</b>\n"
               "3️⃣ Admin tekshirib tasdiqlaydi — obunangiz darhol faollashadi\n\n"
               "<i>Karta raqamini bosib nusxa olishingiz mumkin.</i>\n"
               "Savol bo'lsa: {contact}"),
        "ru": ("Тариф: <b>{plan}</b>\n"
               "Сумма к оплате: <b>{price}</b>\n\n"
               "━━━━━━━━━━━━━━━━━━\n"
               "<b>Номер карты</b>\n"
               "<code>{card}</code>\n"
               "👤 {holder}{bank}\n"
               "━━━━━━━━━━━━━━━━━━\n\n"
               "<b>Что дальше:</b>\n"
               "1️⃣ Переведите <b>{price}</b> на карту выше\n"
               "2️⃣ Отправьте <b>скриншот чека сюда</b>\n"
               "3️⃣ Администратор проверит — подписка активируется сразу\n\n"
               "<i>Нажмите на номер карты, чтобы скопировать.</i>\n"
               "Вопросы: {contact}"),
    },
    "pay_no_card": {
        "uz": ("📨 <b>So'rovingiz qabul qilindi</b>\n\n"
               "Tarif: <b>{plan}</b> — {price}\n\n"
               "To'lov bo'yicha {contact} ga yozing."),
        "ru": ("📨 <b>Заявка принята</b>\n\n"
               "Тариф: <b>{plan}</b> — {price}\n\n"
               "По оплате напишите {contact}."),
    },
    "pay_cancelled": {
        "uz": "To'lov bekor qilindi. Tariflar: /obuna",
        "ru": "Оплата отменена. Тарифы: /obuna",
    },
    "proof_received": {
        "uz": ("✅ <b>Chek qabul qilindi</b>\n\n"
               "Tarif: <b>{plan}</b> — {price}\n\n"
               "Admin tekshirib chiqadi va tasdiqlangach sizga xabar keladi. "
               "Odatda bu bir necha soat ichida bo'ladi.\n\n"
               "Holatni ko'rish: /holat"),
        "ru": ("✅ <b>Чек получен</b>\n\n"
               "Тариф: <b>{plan}</b> — {price}\n\n"
               "Администратор проверит и вы получите уведомление. Обычно это "
               "занимает несколько часов.\n\n"
               "Статус: /holat"),
    },
    "proof_stale": {
        "uz": "Bu so'rov allaqachon hal qilingan. Yangi tarif tanlash: /obuna",
        "ru": "Эта заявка уже обработана. Выбрать тариф заново: /obuna",
    },

    # ---- Holat ----
    "status_owner": {
        "uz": "👑 <b>Bot egasi</b> — cheksiz foydalanish",
        "ru": "👑 <b>Владелец бота</b> — без ограничений",
    },
    "status_sub": {
        "uz": "✅ <b>Obuna faol</b>\nTugash sanasi: {until} ({days} kun qoldi)",
        "ru": "✅ <b>Подписка активна</b>\nДействует до: {until} (осталось {days} дн.)",
    },
    "status_trial": {
        "uz": "🎁 <b>Bepul sinov</b>\nTugash sanasi: {until} ({days} kun qoldi)",
        "ru": "🎁 <b>Пробный период</b>\nДействует до: {until} (осталось {days} дн.)",
    },
    "status_limits": {"uz": "<b>Bugungi limitlar:</b>", "ru": "<b>Лимиты на сегодня:</b>"},
    "status_rows": {"uz": "📒 Bazangizda {n} ta yozuv bor.",
                    "ru": "📒 В вашей базе {n} записей."},
    "status_extend_hint": {
        "uz": ("<i>Obunani hoziroq uzaytirsangiz, qolgan kunlar yo'qolmaydi — "
               "ustiga qo'shiladi.</i>"),
        "ru": ("<i>Продлите сейчас — оставшиеся дни не пропадут, они "
               "прибавятся к новому сроку.</i>"),
    },

    # ---- Byudjet ----
    "budget_intro": {
        "uz": ("💰 <b>Oylik byudjet</b>\n\n"
               "Kategoriyaga oylik chegara qo'ying — oshib ketsa ogohlantiraman.\n\n"
               "<b>O'rnatish:</b>\n"
               "<code>/byudjet oziq-ovqat 2 mln</code>\n"
               "<code>/byudjet transport 500 ming</code>\n\n"
               "<b>O'chirish:</b>\n"
               "<code>/byudjet transport o'chir</code>"),
        "ru": ("💰 <b>Месячный бюджет</b>\n\n"
               "Задайте лимит по категории — предупрежу при превышении.\n\n"
               "<b>Установить:</b>\n"
               "<code>/byudjet oziq-ovqat 2 mln</code>\n"
               "<code>/byudjet transport 500 ming</code>\n\n"
               "<b>Удалить:</b>\n"
               "<code>/byudjet transport o'chir</code>"),
    },
    "budget_title": {"uz": "💰 <b>Shu oylik byudjet</b>", "ru": "💰 <b>Бюджет на месяц</b>"},
    "budget_set": {
        "uz": ("✅ <b>{cat}</b> uchun oylik byudjet: <b>{amount}</b>\n\n"
               "80% va 100% ga yetganda ogohlantiraman."),
        "ru": ("✅ Бюджет на месяц для <b>{cat}</b>: <b>{amount}</b>\n\n"
               "Предупрежу при 80% и 100%."),
    },
    "budget_deleted": {"uz": "🗑 «{cat}» byudjeti o'chirildi.",
                       "ru": "🗑 Бюджет «{cat}» удалён."},
    "budget_bad_amount": {
        "uz": "Summani tushunmadim.\n\nMasalan: <code>/byudjet oziq-ovqat 2 mln</code>",
        "ru": "Не понял сумму.\n\nНапример: <code>/byudjet oziq-ovqat 2 mln</code>",
    },
    "budget_left": {"uz": "qoldi: {amount}", "ru": "осталось: {amount}"},
    "budget_over": {"uz": "⚠️ oshib ketdi: {amount}", "ru": "⚠️ превышено: {amount}"},
    "budget_alert_80": {
        "uz": "🟡 <b>{cat}</b> byudjetining {pct}% i sarflandi.\n\nQoldi: {left}",
        "ru": "🟡 Использовано {pct}% бюджета «{cat}».\n\nОсталось: {left}",
    },
    "budget_alert_100": {
        "uz": ("🔴 <b>{cat}</b> byudjeti oshib ketdi!\n\n"
               "Sarflandi: {spent}\nChegara: {limit}\nOshgan: {over}"),
        "ru": ("🔴 Бюджет «{cat}» превышен!\n\n"
               "Потрачено: {spent}\nЛимит: {limit}\nПревышение: {over}"),
    },

    # ---- Eslatma ----
    "reminder_intro": {
        "uz": ("🔔 <b>Kunlik eslatma</b>\n\n"
               "Har kuni belgilangan vaqtda kunlik xulosangizni yuboraman — "
               "yozishni unutmaslik uchun.\n\n"
               "<b>Yoqish:</b> <code>/eslatma 21</code> (soat 21:00)\n"
               "<b>O'chirish:</b> <code>/eslatma o'chir</code>"),
        "ru": ("🔔 <b>Ежедневное напоминание</b>\n\n"
               "Каждый день в выбранное время буду присылать итог дня — "
               "чтобы вы не забывали записывать.\n\n"
               "<b>Включить:</b> <code>/eslatma 21</code> (21:00)\n"
               "<b>Выключить:</b> <code>/eslatma o'chir</code>"),
    },
    "reminder_on": {
        "uz": ("🔔 Har kuni soat <b>{hour}:00</b> da eslataman.\n\n"
               "O'chirish: <code>/eslatma o'chir</code>"),
        "ru": ("🔔 Буду напоминать каждый день в <b>{hour}:00</b>.\n\n"
               "Выключить: <code>/eslatma o'chir</code>"),
    },
    "reminder_off": {"uz": "🔕 Kunlik eslatma o'chirildi.",
                     "ru": "🔕 Ежедневное напоминание выключено."},
    "reminder_bad_hour": {
        "uz": "Soatni 0 dan 23 gacha kiriting. Masalan: /eslatma 21",
        "ru": "Укажите час от 0 до 23. Например: /eslatma 21",
    },
    "daily_summary": {
        "uz": "🌙 <b>Bugungi xulosa</b>\n\n{n} ta yozuv · {parts}\n\nYana qo'shadigan narsa bormi?",
        "ru": "🌙 <b>Итог дня</b>\n\nЗаписей: {n} · {parts}\n\nЕсть что добавить?",
    },
    "daily_empty": {
        "uz": ("🌙 Bugun hali hech narsa yozmadingiz.\n\n"
               "Esingizga tushgan xarajatni yozib qo'ying — masalan "
               "<code>obedga 45 ming</code>"),
        "ru": ("🌙 Сегодня вы ещё ничего не записали.\n\n"
               "Запишите расход, который вспомните — например "
               "<code>обед 45 тысяч</code>"),
    },

    # ---- Muddat ogohlantirishi ----
    "expiry_trial": {
        "uz": "🎁 <b>Bepul sinovingizga {days} kun qoldi</b>",
        "ru": "🎁 <b>До конца пробного периода {days} дн.</b>",
    },
    "expiry_trial_today": {
        "uz": "🎁 <b>Bepul sinovingiz bugun tugaydi</b>",
        "ru": "🎁 <b>Пробный период заканчивается сегодня</b>",
    },
    "expiry_trial_body": {
        "uz": ("Shu vaqt ichida <b>{n} ta</b> yozuv qildingiz.\n\n"
               "Obuna bo'lsangiz — hammasi joyida qoladi va davom etaverasiz. "
               "Qolgan bepul kunlar yo'qolmaydi."),
        "ru": ("За это время вы сделали <b>{n}</b> записей.\n\n"
               "Оформите подписку — всё сохранится и вы продолжите работу. "
               "Оставшиеся бесплатные дни не пропадут."),
    },
    "expiry_sub": {
        "uz": "⏳ <b>Obunangizga {days} kun qoldi</b>",
        "ru": "⏳ <b>До конца подписки {days} дн.</b>",
    },
    "expiry_sub_today": {
        "uz": "⏳ <b>Obunangiz bugun tugaydi</b>",
        "ru": "⏳ <b>Подписка заканчивается сегодня</b>",
    },
    "expiry_sub_body": {
        "uz": "Uzaytirsangiz, yangi muddat mavjudining ustiga qo'shiladi — bir kun ham yo'qolmaydi.",
        "ru": "При продлении новый срок добавится к текущему — ни один день не пропадёт.",
    },
    "sub_activated": {
        "uz": ("🎉 <b>Obunangiz faollashtirildi!</b>\n\n"
               "Tarif: {plan}\nAmal qilish muddati: <b>{until}</b>\n\n"
               "Rahmat! Holatni ko'rish: /holat"),
        "ru": ("🎉 <b>Подписка активирована!</b>\n\n"
               "Тариф: {plan}\nДействует до: <b>{until}</b>\n\n"
               "Спасибо! Статус: /holat"),
    },

    # ---- Referal ----
    "referral": {
        "uz": ("🎁 <b>Do'stingizni taklif qiling</b>\n\n"
               "Havolangiz orqali kelgan har bir do'st uchun "
               "<b>ikkalangizga {bonus} kundan</b> bepul foydalanish qo'shiladi.\n\n"
               "<b>Sizning havolangiz:</b>\n<code>{link}</code>\n\n"
               "📊 Taklif qilganingiz: <b>{invited} ta</b>\n"
               "🎁 Yig'ilgan bonus: <b>{bonus_days} kun</b>"),
        "ru": ("🎁 <b>Пригласите друга</b>\n\n"
               "За каждого друга по вашей ссылке <b>вам обоим по {bonus} дней</b> "
               "бесплатного доступа.\n\n"
               "<b>Ваша ссылка:</b>\n<code>{link}</code>\n\n"
               "📊 Приглашено: <b>{invited}</b>\n"
               "🎁 Накоплено бонусов: <b>{bonus_days} дн.</b>"),
    },
    "referral_share_btn": {"uz": "📨 Do'stga yuborish", "ru": "📨 Отправить другу"},
    "referral_share_text": {
        "uz": ("Men xarajatlarimni shu bot bilan yuritaman — oddiy tilda "
               "yozasiz, u o'zi kategoriyaga ajratadi. Chek rasmini ham o'qiydi."),
        "ru": ("Веду расходы в этом боте — пишешь обычным текстом, он сам "
               "раскладывает по категориям. И чеки по фото распознаёт."),
    },
    "referral_welcome": {
        "uz": "🎁 Taklif havolasi orqali kirdingiz — bepul muddatingizga <b>{bonus} kun</b> qo'shildi!",
        "ru": "🎁 Вы пришли по приглашению — к бесплатному периоду добавлено <b>{bonus} дн.</b>!",
    },
    "referral_thanks": {
        "uz": ("🎉 <b>{name}</b> sizning havolangiz orqali qo'shildi!\n\n"
               "Sizga <b>{bonus} kun</b> bepul foydalanish qo'shildi. Rahmat!"),
        "ru": ("🎉 <b>{name}</b> присоединился по вашей ссылке!\n\n"
               "Вам добавлено <b>{bonus} дн.</b> бесплатного доступа. Спасибо!"),
    },

    # ---- Hisobni o'chirish ----
    "erase_confirm": {
        "uz": ("⚠️ <b>Hisobni butunlay o'chirish</b>\n\n"
               "O'chiriladi:\n• {n} ta moliyaviy yozuv\n"
               "• Byudjetlar va qarz tarixi\n• Obuna va sarf tarixi\n• Hisobingiz\n\n"
               "<b>Bu amalni qaytarib bo'lmaydi.</b>\n\n"
               "Avval ma'lumotingizni saqlab olishni tavsiya qilaman."),
        "ru": ("⚠️ <b>Полное удаление аккаунта</b>\n\n"
               "Будет удалено:\n• {n} финансовых записей\n"
               "• Бюджеты и история долгов\n• История подписки и расходов\n• Аккаунт\n\n"
               "<b>Отменить это будет невозможно.</b>\n\n"
               "Рекомендую сначала сохранить свои данные."),
    },
    "erase_btn_csv": {"uz": "📤 Avval CSV yuklab olaman",
                      "ru": "📤 Сначала скачаю CSV"},
    "erase_btn_yes": {"uz": "🗑 Ha, hammasini o'chir",
                      "ru": "🗑 Да, удалить всё"},
    "erase_btn_no": {"uz": "❌ Bekor qilish", "ru": "❌ Отмена"},
    "erase_cancelled": {"uz": "✅ Bekor qilindi — hech narsa o'chirilmadi.",
                        "ru": "✅ Отменено — ничего не удалено."},
    "erase_done": {
        "uz": ("🗑 <b>Hisobingiz o'chirildi</b>\n\n"
               "{n} ta yozuv va butun tarix bazadan olib tashlandi.\n\n"
               "Yana foydalanmoqchi bo'lsangiz — /start bosing.\n\nRahmat!"),
        "ru": ("🗑 <b>Аккаунт удалён</b>\n\n"
               "{n} записей и вся история удалены из базы.\n\n"
               "Захотите вернуться — нажмите /start.\n\nСпасибо!"),
    },
    "erase_expired": {
        "uz": "Muddat o'tdi. /ochirish ni qaytadan yuboring.",
        "ru": "Время истекло. Отправьте /ochirish заново.",
    },

    # ---- Ulashish ----
    "share_btn": {"uz": "🖼 Rasm qilib ulashish", "ru": "🖼 Поделиться картинкой"},
    "share_caption": {
        "uz": "📊 Hisobotingiz. Do'stlaringizga ulashsangiz bo'ladi!",
        "ru": "📊 Ваш отчёт. Можете поделиться с друзьями!",
    },
}


def _resolve(entry: dict, lang: str, fallback: str) -> str:
    """Kerakli tildagi matnni beradi. Kirill uchun lotinchasidan o'giradi."""
    if lang == "uzc":
        return translit.to_cyrillic(entry.get("uz") or fallback)
    return entry.get(lang) or entry.get(DEFAULT) or fallback


def t(lang: str | None, key: str, **kwargs) -> str:
    """Kalit bo'yicha matn. Tarjima topilmasa o'zbekchasi qaytariladi."""
    entry = T.get(key)
    if entry is None:
        return key
    text = _resolve(entry, normalize(lang), key)
    # O'rin egallovchilar o'girishdan keyin to'ldiriladi — ichidagi qiymat
    # (sana, summa) transliteratsiyaga tushmasligi kerak.
    return text.format(**kwargs) if kwargs else text


def btn(lang: str | None, key: str) -> str:
    return _resolve(BUTTONS.get(key, {}), normalize(lang), key)


def cyr(lang: str | None, text: str) -> str:
    """Tarjima jadvalidan tashqaridagi o'zbekcha matnni kerak bo'lsa o'giradi.

    Uzun qo'llanma va hisobot sarlavhalari kabi joylar uchun.
    """
    return translit.to_cyrillic(text) if normalize(lang) == "uzc" else text


def menu_lookup() -> dict[str, str]:
    """Barcha tildagi tugma matnlarini kalitga bog'laydi.

    Foydalanuvchi tilni almashtirsa, eski klaviatura hali ekranda turgan
    bo'lishi mumkin — shuning uchun ikkala til ham qabul qilinadi.
    """
    out: dict[str, str] = {}
    for key, variants in BUTTONS.items():
        for text in variants.values():
            out[text] = key
        # Kirill yozuvidagi variant ham qabul qilinsin.
        out[translit.to_cyrillic(variants.get("uz", ""))] = key
    out.pop("", None)
    return out
