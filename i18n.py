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
               "Men Tanga — sizning shaxsiy hisobingiz. Xarajatlaringizni yozib "
               "boraman, kategoriyalarga ajrataman va hisobot beraman.\n\n"
               "<b>Boshlash juda oddiy — shunchaki menga yozing:</b>\n\n"
               "<code>obedga 45 ming</code>\n\n"
               "Tugmani bosib sinab ko'ring 👇"),
        "ru": ("👋 <b>Здравствуйте{name}!</b>\n\n"
               "Я Tanga — ваш личный учёт финансов. Записываю расходы, распределяю "
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
               "2️⃣ To'lov chekini shu yerga yuboring — <b>skrinshot rasm "
               "yoki PDF</b>\n"
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
               "2️⃣ Отправьте чек сюда — <b>скриншот или PDF</b>\n"
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
    # Ikkinchi bosqich: tugmani bexosdan bosib yuborish oson, so'zni
    # ataylab yozish esa qiyin. Shuning uchun oxirgi tasdiq — yozma.
    "erase_word": {"uz": "O'CHIRISH", "ru": "УДАЛИТЬ"},
    "erase_type": {
        "uz": ("🛑 <b>Oxirgi tasdiq</b>\n\n"
               "{n} ta yozuv va butun hisobingiz o'chiriladi. Buni "
               "qaytarib bo'lmaydi.\n\n"
               "Rostdan xohlasangiz — javob sifatida shu so'zni yozing:\n"
               "<code>{word}</code>\n\n"
               "Boshqa har qanday xabar — bekor qilish. 5 daqiqadan keyin "
               "so'rov o'z-o'zidan bekor bo'ladi."),
        "ru": ("🛑 <b>Последнее подтверждение</b>\n\n"
               "{n} записей и весь аккаунт будут удалены. Это необратимо.\n\n"
               "Если действительно хотите — отправьте в ответ это слово:\n"
               "<code>{word}</code>\n\n"
               "Любое другое сообщение — отмена. Через 5 минут запрос "
               "отменится сам."),
    },
    "erase_wrong_word": {
        "uz": ("✅ Bekor qilindi — hech narsa o'chirilmadi.\n\n"
               "So'z mos kelmadi. Yozuvlaringiz joyida."),
        "ru": ("✅ Отменено — ничего не удалено.\n\n"
               "Слово не совпало. Ваши записи на месте."),
    },
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

    # ---- Rozilik (shaxsiy ma'lumotni qayta ishlashdan oldin) ----
    "consent": {
        "uz": ("👋 <b>Boshlashdan oldin</b>\n\n"
               "Men sizning moliyaviy yozuvlaringizni saqlayman va tahlil "
               "qilaman. Qonun talabiga ko'ra buni boshlashdan oldin "
               "roziligingizni olishim kerak.\n\n"
               "<b>Nima saqlanadi</b>\n"
               "Telegram ID va ismingiz, siz yozgan summalar, kategoriyalar, "
               "izohlar, qarzdorlar ismi, obuna va to'lov tarixi.\n\n"
               "<b>Qayerda saqlanadi</b>\n"
               "Yevropadagi ijaraga olingan serverda (Fransiya). Har kuni "
               "shifrlangan zaxira nusxa olinadi.\n\n"
               "<b>Kimga uzatiladi</b>\n"
               "Yozganingizni tushunish uchun matn va chek rasmi "
               "<b>Anthropic</b> (AQSh) xizmatiga yuboriladi. U yerda "
               "saqlanmaydi va modelni o'qitishga ishlatilmaydi. Boshqa hech "
               "kimga berilmaydi va sotilmaydi.\n\n"
               "<b>Sizning huquqlaringiz</b>\n"
               "• /csv — barcha ma'lumotingizni yuklab olish\n"
               "• /ochirish — hisobni va butun tarixni butunlay o'chirish\n"
               "• /maxfiylik — to'liq siyosat\n"
               "• /shartlar — xizmat shartlari va to'lov qoidalari\n\n"
               "<b>Muhim:</b> men moliyaviy maslahat bermayman — faqat "
               "sizning yozuvlaringizni hisoblab beraman.\n\n"
               "Davom etish uchun roziligingizni bildiring 👇"),
        "ru": ("👋 <b>Перед началом</b>\n\n"
               "Я храню и анализирую ваши финансовые записи. По закону я "
               "обязан получить ваше согласие до начала обработки.\n\n"
               "<b>Что хранится</b>\n"
               "Telegram ID и имя, введённые вами суммы, категории, "
               "комментарии, имена должников, история подписки и оплат.\n\n"
               "<b>Где хранится</b>\n"
               "На арендованном сервере в Европе (Франция). Каждый день "
               "создаётся зашифрованная резервная копия.\n\n"
               "<b>Кому передаётся</b>\n"
               "Чтобы понять написанное, текст и фото чека отправляются в "
               "сервис <b>Anthropic</b> (США). Там они не сохраняются и не "
               "используются для обучения модели. Больше никому не "
               "передаются и не продаются.\n\n"
               "<b>Ваши права</b>\n"
               "• /csv — скачать все свои данные\n"
               "• /ochirish — полностью удалить аккаунт и всю историю\n"
               "• /maxfiylik — полная политика\n"
               "• /shartlar — условия сервиса и правила оплаты\n\n"
               "<b>Важно:</b> я не даю финансовых советов — только считаю "
               "ваши записи.\n\n"
               "Чтобы продолжить, подтвердите согласие 👇"),
    },
    "consent_yes": {"uz": "✅ Roziman, davom etamiz",
                    "ru": "✅ Согласен, продолжим"},
    "consent_privacy": {"uz": "🔒 Maxfiylik", "ru": "🔒 Конфиденциальность"},
    "consent_terms": {"uz": "📄 Shartlar", "ru": "📄 Условия"},
    "consent_done": {"uz": "Rahmat! Endi boshlaymiz.",
                     "ru": "Спасибо! Теперь начнём."},
    "consent_needed": {
        "uz": "Avval roziligingiz kerak — /start bosing.",
        "ru": "Сначала нужно ваше согласие — нажмите /start.",
    },

    # ---- Xizmat shartlari (ommaviy oferta) ----
    "terms": {
        "uz": ("📄 <b>XIZMAT SHARTLARI</b>\n\n"
               "<b>1. Xizmat nima</b>\n"
               "«Tanga» — shaxsiy xarajatlarni yozib borish va hisobot "
               "olish uchun Telegram boti. Xizmat «bor holicha» taqdim "
               "etiladi.\n\n"
               "<b>2. Bepul sinov</b>\n"
               "Har bir yangi foydalanuvchi {trial} kun bepul foydalanadi. "
               "Sinov davrida hech qanday to'lov talab qilinmaydi.\n\n"
               "<b>3. Obuna va to'lov</b>\n"
               "• Tariflar: /obuna\n"
               "• To'lov karta o'tkazmasi orqali amalga oshiriladi\n"
               "• To'lovdan so'ng chek (rasm yoki PDF) yuboriladi\n"
               "• Administrator tasdiqlagach obuna faollashadi\n"
               "• Yangi muddat mavjud muddat ustiga qo'shiladi\n"
               "• To'lov <b>avtomatik yangilanmaydi</b> — har safar o'zingiz "
               "qaror qilasiz\n\n"
               "<b>4. Pulni qaytarish</b>\n"
               "Obuna faollashganidan keyin <b>3 kun ichida</b> xizmatdan "
               "foydalanmagan bo'lsangiz, to'liq qaytariladi. Undan keyin "
               "foydalanilmagan kunlar uchun qisman qaytarish ko'rib "
               "chiqiladi. Murojaat: {contact}\n\n"
               "<b>5. Xizmat to'xtatilishi</b>\n"
               "Botni suiiste'mol qilish (avtomatlashtirilgan spam, tizimga "
               "zarar yetkazishga urinish) aniqlansa, hisob bloklanishi "
               "mumkin. Bunda qolgan obuna kunlari qaytariladi.\n\n"
               "<b>6. Aniqlik va javobgarlik</b>\n"
               "Bot summalarni <b>dastur bilan</b> hisoblaydi, AI faqat "
               "matnni o'qiydi va kategoriyaga ajratadi. Shunga qaramay xato "
               "bo'lishi mumkin — muhim qarorlardan oldin sonlarni o'zingiz "
               "tekshiring. Bot moliyaviy, investitsiya yoki soliq maslahati "
               "<b>bermaydi</b>. Xizmat ma'lumotlariga tayanib qilingan "
               "qarorlar uchun javobgarlik foydalanuvchida.\n\n"
               "<b>7. Ma'lumot va maxfiylik</b>\n"
               "/maxfiylik da to'liq yozilgan. Istalgan paytda /ochirish "
               "bilan hammasini o'chira olasiz.\n\n"
               "<b>8. Shartlar o'zgarishi</b>\n"
               "Shartlar o'zgarsa, botda xabar beriladi va roziligingiz "
               "qaytadan so'raladi.\n\n"
               "<b>Aloqa:</b> {contact}\n"
               "<i>Versiya: {version}</i>"),
        "ru": ("📄 <b>УСЛОВИЯ СЕРВИСА</b>\n\n"
               "<b>1. Что это за сервис</b>\n"
               "«Tanga» — Telegram-бот для учёта личных расходов и "
               "получения отчётов. Сервис предоставляется «как есть».\n\n"
               "<b>2. Бесплатный период</b>\n"
               "Каждый новый пользователь получает {trial} дней бесплатно. "
               "В пробный период оплата не требуется.\n\n"
               "<b>3. Подписка и оплата</b>\n"
               "• Тарифы: /obuna\n"
               "• Оплата производится переводом на карту\n"
               "• После оплаты отправляется чек (фото или PDF)\n"
               "• Подписка активируется после подтверждения администратором\n"
               "• Новый срок добавляется к текущему\n"
               "• Оплата <b>не продлевается автоматически</b> — вы решаете "
               "каждый раз сами\n\n"
               "<b>4. Возврат средств</b>\n"
               "Если в течение <b>3 дней</b> после активации вы не "
               "пользовались сервисом — возврат в полном объёме. После "
               "этого рассматривается частичный возврат за неиспользованные "
               "дни. Обращение: {contact}\n\n"
               "<b>5. Прекращение обслуживания</b>\n"
               "При злоупотреблении (автоматизированный спам, попытки "
               "навредить системе) аккаунт может быть заблокирован. "
               "Оставшиеся дни подписки при этом возвращаются.\n\n"
               "<b>6. Точность и ответственность</b>\n"
               "Суммы считает <b>программа</b>, ИИ только читает текст и "
               "распределяет по категориям. Тем не менее ошибки возможны — "
               "проверяйте цифры перед важными решениями. Бот <b>не даёт</b> "
               "финансовых, инвестиционных или налоговых советов. "
               "Ответственность за решения, принятые на основе данных "
               "сервиса, лежит на пользователе.\n\n"
               "<b>7. Данные и конфиденциальность</b>\n"
               "Подробно в /maxfiylik. В любой момент можете удалить всё "
               "через /ochirish.\n\n"
               "<b>8. Изменение условий</b>\n"
               "При изменении условий бот сообщит об этом и заново запросит "
               "ваше согласие.\n\n"
               "<b>Контакт:</b> {contact}\n"
               "<i>Версия: {version}</i>"),
    },

    "terms_operator": {
        "uz": "<b>Xizmat ko'rsatuvchi:</b> {operator}",
        "ru": "<b>Исполнитель:</b> {operator}",
    },

    # ---- Maxfiylik siyosati ----
    "privacy": {
        "uz": ("🔒 <b>MAXFIYLIK SIYOSATI</b>\n\n"
               "<b>Qanday ma'lumot saqlanadi</b>\n"
               "• Telegram ID, ismingiz va username\n"
               "• Siz yozgan xarajat/kirim yozuvlari: summa, kategoriya, "
               "izoh, sana\n"
               "• Qarz yozuvlarida siz ko'rsatgan shaxs ismi\n"
               "• Obuna muddati va to'lov tarixi\n\n"
               "<b>Chek rasmlari</b>\n"
               "Chek suratini yuborsangiz, u <b>faqat o'qish uchun</b> "
               "Anthropic (AQSh) serveriga yuboriladi. Rasm bizda ham, u "
               "yerda ham saqlanmaydi — o'qilgandan keyin darhol o'chadi. "
               "Faqat undan chiqqan <b>matnli yozuvlar</b> sizning "
               "bazangizda qoladi.\n\n"
               "Yozgan matnlaringiz ham xuddi shu tarzda tahlil uchun "
               "yuboriladi. Anthropic bu ma'lumotni modelni o'qitishga "
               "ishlatmaydi.\n\n"
               "<b>Kim ko'ra oladi</b>\n"
               "• Siz — bot va boshqaruv paneli orqali\n"
               "• Texnik xizmat ko'rsatuvchi administrator — nosozlikni "
               "tuzatish uchun\n"
               "• Boshqa foydalanuvchilar sizning ma'lumotingizni "
               "<b>hech qachon</b> ko'rmaydi. Har bir yozuv Telegram ID "
               "bo'yicha ajratilgan.\n\n"
               "<b>Qayerda saqlanadi</b>\n"
               "Fransiyadagi ijaraga olingan serverda (Contabo). Kirish "
               "faqat SSH kaliti orqali, parol bilan kirish o'chirilgan. "
               "Har kuni AES-256 bilan shifrlangan zaxira nusxa olinadi.\n\n"
               "<b>Qancha saqlanadi</b>\n"
               "Siz o'chirmaguningizcha. /ochirish bosilganda darhol va "
               "butunlay o'chiriladi; zaxira nusxalar 14 kun ichida "
               "almashib ketadi.\n\n"
               "<b>Sizning huquqlaringiz</b>\n"
               "• /csv — barcha ma'lumotingizni fayl qilib olish\n"
               "• /ochirish — hisobni va butun tarixni butunlay o'chirish "
               "(darhol va qaytarib bo'lmaydigan tarzda)\n"
               "• Roziligingizni istalgan paytda qaytarib olishingiz "
               "mumkin — buning uchun /ochirish bosing\n\n"
               "<b>To'lov</b>\n"
               "Karta ma'lumotlaringiz bizga kelmaydi. Siz o'zingiz "
               "o'tkazma qilasiz va faqat chek skrinshotini yuborasiz.\n\n"
               "Savol: {contact}"),
        "ru": ("🔒 <b>ПОЛИТИКА КОНФИДЕНЦИАЛЬНОСТИ</b>\n\n"
               "<b>Какие данные хранятся</b>\n"
               "• Telegram ID, имя и username\n"
               "• Ваши записи расходов/доходов: сумма, категория, "
               "комментарий, дата\n"
               "• Имя человека, указанное в записях о долге\n"
               "• Срок подписки и история оплат\n\n"
               "<b>Фото чеков</b>\n"
               "Отправленное фото чека передаётся на сервер Anthropic (США) "
               "<b>только для распознавания</b>. Изображение не хранится ни "
               "у нас, ни там — удаляется сразу после прочтения. В вашей "
               "базе остаются только полученные <b>текстовые записи</b>.\n\n"
               "Ваши текстовые сообщения передаются на анализ так же. "
               "Anthropic не использует эти данные для обучения модели.\n\n"
               "<b>Кто может видеть</b>\n"
               "• Вы — через бот и панель управления\n"
               "• Администратор технической поддержки — для устранения "
               "неполадок\n"
               "• Другие пользователи <b>никогда</b> не видят ваши данные. "
               "Все записи разделены по Telegram ID.\n\n"
               "<b>Где хранится</b>\n"
               "На арендованном сервере во Франции (Contabo). Доступ только "
               "по SSH-ключу, вход по паролю отключён. Каждый день "
               "создаётся резервная копия с шифрованием AES-256.\n\n"
               "<b>Сколько хранится</b>\n"
               "Пока вы сами не удалите. По команде /ochirish данные "
               "удаляются немедленно и полностью; резервные копии "
               "перезаписываются в течение 14 дней.\n\n"
               "<b>Ваши права</b>\n"
               "• /csv — выгрузить все свои данные файлом\n"
               "• /ochirish — полностью удалить аккаунт и всю историю "
               "(сразу и безвозвратно)\n"
               "• Вы можете отозвать согласие в любой момент — для этого "
               "нажмите /ochirish\n\n"
               "<b>Оплата</b>\n"
               "Данные вашей карты к нам не попадают. Перевод вы делаете "
               "сами и присылаете только скриншот чека.\n\n"
               "Вопросы: {contact}"),
    },

    # ---- Ketma-ket kunlar (streak) ----
    "streak_grew": {
        "uz": "🔥 Ketma-ket {n} kun yozyapsiz!",
        "ru": "🔥 {n} дней подряд ведёте учёт!",
    },
    "streak_record": {
        "uz": "🏆 Yangi rekord: ketma-ket {n} kun!",
        "ru": "🏆 Новый рекорд: {n} дней подряд!",
    },
    "streak_7": {
        "uz": ("🎉 <b>Bir hafta to'xtovsiz!</b>\n"
               "Odat shakllanishi shu yerdan boshlanadi. Davom eting."),
        "ru": ("🎉 <b>Неделя без пропусков!</b>\n"
               "Именно так формируется привычка. Продолжайте."),
    },
    "streak_30": {
        "uz": ("🏅 <b>30 kun ketma-ket!</b>\n"
               "Endi bu odat. /oy bosib bir oylik manzarani ko'ring."),
        "ru": ("🏅 <b>30 дней подряд!</b>\n"
               "Теперь это привычка. Нажмите /oy и посмотрите картину "
               "за месяц."),
    },
    "streak_100": {
        "uz": "💎 <b>100 kun!</b> Bu allaqachon jiddiy natija. Tabriklayman!",
        "ru": "💎 <b>100 дней!</b> Это уже серьёзный результат. Поздравляю!",
    },
    "entries_milestone": {
        "uz": ("✨ <b>{n}-yozuv!</b> Endi ma'lumot yetarli — "
               "«{btn}» bosib manzarani ko'ring."),
        "ru": ("✨ <b>{n}-я запись!</b> Данных уже достаточно — "
               "нажмите «{btn}» и посмотрите картину."),
    },

    # ---- Haftalik xulosa ----
    "digest_head": {
        "uz": "📬 <b>Haftalik xulosa</b>\n<i>{start} — {end}</i>",
        "ru": "📬 <b>Итоги недели</b>\n<i>{start} — {end}</i>",
    },
    "digest_body": {
        "uz": "\n\n💸 Chiqim: <b>{spent}</b>\n🧾 Yozuvlar: {count} ta",
        "ru": "\n\n💸 Расходы: <b>{spent}</b>\n🧾 Записей: {count}",
    },
    "digest_less": {
        "uz": "\n📉 O'tgan haftadan <b>{pct}% kam</b> — barakalla!",
        "ru": "\n📉 На <b>{pct}% меньше</b>, чем на прошлой неделе — отлично!",
    },
    "digest_more": {
        "uz": "\n📈 O'tgan haftadan <b>{pct}% ko'p</b>.",
        "ru": "\n📈 На <b>{pct}% больше</b>, чем на прошлой неделе.",
    },
    "digest_top": {"uz": "\n\n<b>Eng ko'p sarflangan:</b>",
                   "ru": "\n\n<b>Больше всего потрачено:</b>"},
    "digest_streak": {
        "uz": "\n\n🔥 Ketma-ket {n} kun. Zanjirni uzmang!",
        "ru": "\n\n🔥 {n} дней подряд. Не прерывайте цепочку!",
    },
    "digest_tip": {
        "uz": "\n\n💡 Byudjet qo'ysangiz, chegaraga yaqinlashganda "
              "ogohlantiraman: /byudjet",
        "ru": "\n\n💡 Поставьте бюджет — предупрежу при приближении "
              "к лимиту: /byudjet",
    },

    # ---- Qaytarish xabari ----
    "winback": {
        "uz": ("👋 Ancha vaqtdan beri yozmadingiz — {days} kun bo'ldi.\n\n"
               "Yozilmagan xarajat — ko'rinmaydigan xarajat. Bugungisini "
               "bitta xabar bilan tiklab qo'ying:\n\n"
               "<code>obedga 45 ming</code>\n\n"
               "Obunangiz hali faol, bemalol foydalaning."),
        "ru": ("👋 Вы давно не записывали — прошло {days} дней.\n\n"
               "Незаписанный расход — незаметный расход. Восстановите "
               "сегодняшний одним сообщением:\n\n"
               "<code>обед 45 тысяч</code>\n\n"
               "Подписка ещё активна, пользуйтесь спокойно."),
    },
    "winback_best": {
        "uz": "\n\n🔥 Eng uzun zanjiringiz — {n} kun. Yangisini boshlaymizmi?",
        "ru": "\n\n🔥 Ваша лучшая серия — {n} дней. Начнём новую?",
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
