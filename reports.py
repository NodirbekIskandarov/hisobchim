"""Hisobotlarni matnga aylantirish va sana oraliqlarini hisoblash.

Telegram'ga HTML parse_mode bilan yuboriladi, shuning uchun foydalanuvchi
kiritgan har qanday matn esc() orqali o'tkaziladi.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from html import escape

import config
import db

UZ_MONTHS = [
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
]


def esc(text) -> str:
    return escape(str(text or ""), quote=False)


def today() -> date:
    return datetime.now(config.TZ).date()


def fmt_money(value: float) -> str:
    """1250000 -> "1 250 000 so'm" """
    rounded = round(float(value))
    return f"{rounded:,}".replace(",", " ") + f" {config.CURRENCY}"


def fmt_date(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
    except (ValueError, TypeError):
        return str(iso)
    return f"{d.day}-{UZ_MONTHS[d.month - 1]}"


def period_range(period: str, ref: date | None = None) -> tuple[date, date, str]:
    """period: bugun | kecha | hafta | oy | otgan_oy | yil"""
    ref = ref or today()
    if period == "bugun":
        return ref, ref, "Bugun"
    if period == "kecha":
        y = ref - timedelta(days=1)
        return y, y, "Kecha"
    if period == "hafta":
        start = ref - timedelta(days=ref.weekday())
        return start, ref, "Shu hafta"
    if period == "oy":
        return ref.replace(day=1), ref, f"{UZ_MONTHS[ref.month - 1].capitalize()} oyi"
    if period == "otgan_oy":
        last_day_prev = ref.replace(day=1) - timedelta(days=1)
        start = last_day_prev.replace(day=1)
        return start, last_day_prev, f"{UZ_MONTHS[start.month - 1].capitalize()} oyi"
    if period == "yil":
        return ref.replace(month=1, day=1), ref, f"{ref.year}-yil"
    return ref.replace(day=1), ref, "Davr"


def _bar(share: float, width: int = 10) -> str:
    filled = max(0, min(width, round(share * width)))
    return "█" * filled + "░" * (width - filled)


def summary_text(user_id: int, period: str) -> str:
    start, end, label = period_range(period)
    t = db.totals(user_id, start, end)
    kirim = t[config.KIND_KIRIM]
    chiqim = t[config.KIND_CHIQIM]
    balans = kirim - chiqim

    lines = [f"📊 <b>{esc(label)}</b>", ""]
    lines.append(f"🔺 Kirim:  {fmt_money(kirim)}")
    lines.append(f"🔻 Chiqim: {fmt_money(chiqim)}")
    lines.append(f"{'🟢' if balans >= 0 else '🔴'} Farq:   {fmt_money(balans)}")

    cats = db.by_category(user_id, start, end, config.KIND_CHIQIM)
    if cats:
        lines.append("")
        lines.append("<b>Chiqim kategoriyalari:</b>")
        for name, total, cnt in cats[:8]:
            share = total / chiqim if chiqim else 0
            icon = config.CATEGORY_ICONS.get(name, "•")
            lines.append(f"{icon} {esc(name)} — {fmt_money(total)} ({share * 100:.0f}%)")
            lines.append(f"   <code>{_bar(share)}</code> {cnt} ta")

    qarz_berdim = t[config.KIND_QARZ_BERDIM]
    qarz_oldim = t[config.KIND_QARZ_OLDIM]
    if qarz_berdim or qarz_oldim:
        lines.append("")
        if qarz_berdim:
            lines.append(f"📤 Qarz berdim: {fmt_money(qarz_berdim)}")
        if qarz_oldim:
            lines.append(f"📥 Qarz oldim: {fmt_money(qarz_oldim)}")

    if not cats and not kirim and not qarz_berdim and not qarz_oldim:
        lines.append("")
        lines.append("<i>Bu davrda yozuv yo'q.</i>")
    elif chiqim and (end - start).days >= 2:
        days = (end - start).days + 1
        lines.append("")
        lines.append(f"<i>Kuniga o'rtacha: {fmt_money(chiqim / days)}</i>")

    return "\n".join(lines)


def transaction_line(row, with_id: bool = True) -> str:
    icon = config.KIND_ICONS.get(row["kind"], "•")
    cat_icon = config.CATEGORY_ICONS.get(row["category"], "")
    note = row["note"] or row["category"]
    person = f" — {esc(row['person'])}" if row["person"] else ""
    tail = f" <code>#{row['id']}</code>" if with_id else ""
    return (
        f"{icon} {fmt_money(row['amount'])} · {cat_icon} {esc(note)}{person}"
        f" · <i>{fmt_date(row['occurred_on'])}</i>{tail}"
    )


def recent_text(user_id: int, limit: int = 10) -> str:
    rows = db.recent(user_id, limit)
    if not rows:
        return "Hozircha yozuv yo'q."
    lines = [f"🧾 <b>Oxirgi {len(rows)} ta yozuv</b>", ""]
    lines += [transaction_line(r) for r in rows]
    lines.append("")
    lines.append("<i>O'chirish uchun:</i> <code>/ochir 12</code>")
    return "\n".join(lines)


def debts_text(user_id: int) -> str:
    rows = db.open_debts(user_id)
    if not rows:
        return "🤝 Ochiq qarz yo'q."

    berdim = [r for r in rows if r["kind"] == config.KIND_QARZ_BERDIM]
    oldim = [r for r in rows if r["kind"] == config.KIND_QARZ_OLDIM]

    lines = ["🤝 <b>Qarzlar</b>", ""]
    for title, group in (
        ("📤 <b>Menga qarzdorlar</b>", berdim),
        ("📥 <b>Men qarzdorman</b>", oldim),
    ):
        if not group:
            continue
        total = sum(r["amount"] for r in group)
        lines.append(f"{title} — {fmt_money(total)}")
        for r in group:
            who = esc(r["person"] or "noma'lum")
            lines.append(
                f"   • {who}: {fmt_money(r['amount'])}"
                f" ({fmt_date(r['occurred_on'])}) <code>#{r['id']}</code>"
            )
        lines.append("")

    lines.append("<i>Yopish uchun:</i> <code>/yopdim 12</code>")
    return "\n".join(lines)


def receipt_text(data: dict, day_total: float | None = None) -> str:
    """Chek tahlili: kategoriyalar kesimi, tekshiruv natijasi, to'liq ro'yxat."""
    items = data["mahsulotlar"]
    check = data["tekshiruv"]
    total = check["hisoblangan"]

    head = "🧾 <b>Chek qabul qilindi</b>"
    if data["dokon"]:
        head = f"🧾 <b>{esc(data['dokon'])}</b>"
    lines = [head, f"📅 {fmt_date(data['sana'])} · {len(items)} ta mahsulot", ""]

    # Kategoriyalar kesimi — foizli diagramma bilan.
    by_cat: dict[str, list[float]] = {}
    for item in items:
        by_cat.setdefault(item["kategoriya"], []).append(item["summa"])

    lines.append("<b>Kategoriyalar bo'yicha:</b>")
    for name, amounts in sorted(by_cat.items(), key=lambda kv: sum(kv[1]), reverse=True):
        subtotal = sum(amounts)
        share = subtotal / total if total else 0
        icon = config.CATEGORY_ICONS.get(name, "•")
        lines.append(
            f"{icon} {esc(name)} — {fmt_money(subtotal)} ({share * 100:.0f}%)"
        )
        lines.append(f"   <code>{_bar(share)}</code> {len(amounts)} ta")

    lines.append("")
    lines.append(f"💵 <b>Mahsulotlar jami: {fmt_money(total)}</b>")

    if data.get("chegirma"):
        lines.append(f"🏷 Chegirma: −{fmt_money(data['chegirma'])}")

    # Tekshiruv — chekdagi JAMI bilan solishtirish.
    if check["holat"] == "mos":
        lines.append(f"✅ Chekdagi jami bilan mos: {fmt_money(check['chekdagi'])}")
    elif check["holat"] == "farqli":
        lines.append(f"⚠️ Chekdagi jami: {fmt_money(check['chekdagi'])}")
        farq = check["farq"]
        yon = "ortiq" if farq > 0 else "kam"
        lines.append(
            f"   <i>Farq: {fmt_money(abs(farq))} {yon} chiqdi — "
            f"ba'zi qatorlar noto'g'ri o'qilgan bo'lishi mumkin.</i>"
        )
    else:
        lines.append("<i>ℹ️ Chekda yakuniy summa ko'rinmadi — tekshirib bo'lmadi.</i>")

    # Eng qimmat mahsulot — tahlil uchun foydali.
    if len(items) > 1:
        top = max(items, key=lambda i: i["summa"])
        lines.append(
            f"🔝 Eng qimmati: {esc(top['nomi'])} — {fmt_money(top['summa'])}"
        )

    if day_total:
        lines.append("")
        lines.append(f"<i>Bugungi umumiy chiqim: {fmt_money(day_total)}</i>")

    return "\n".join(lines)


def receipt_items_text(rows) -> str:
    """Chekdagi mahsulotlarning to'liq ro'yxati (alohida xabar uchun)."""
    if not rows:
        return "Bu chek uchun yozuv topilmadi."
    lines = [f"🧾 <b>To'liq ro'yxat</b> — {len(rows)} ta", ""]
    for r in rows:
        icon = config.CATEGORY_ICONS.get(r["category"], "•")
        lines.append(
            f"{icon} {esc(r['note'] or r['category'])} — {fmt_money(r['amount'])}"
            f" <code>#{r['id']}</code>"
        )
    lines.append("")
    lines.append("<i>Bittasini o'chirish:</i> <code>/ochir 12</code>")
    return "\n".join(lines)


def saved_text(rows: list[dict]) -> str:
    """Saqlangandan keyin ko'rsatiladigan tasdiq matni."""
    if len(rows) == 1:
        r = rows[0]
        icon = config.KIND_ICONS[r["turi"]]
        cat_icon = config.CATEGORY_ICONS.get(r["kategoriya"], "")
        body = [
            f"{icon} <b>{esc(config.KIND_LABELS[r['turi']])}</b> saqlandi",
            f"💵 {fmt_money(r['summa'])}",
            f"{cat_icon} {esc(r['kategoriya'])}",
        ]
        if r.get("izoh"):
            body.append(f"📝 {esc(r['izoh'])}")
        if r.get("shaxs"):
            body.append(f"👤 {esc(r['shaxs'])}")
        body.append(f"📅 {fmt_date(r['sana'])}")
        return "\n".join(body)

    lines = [f"✅ <b>{len(rows)} ta yozuv saqlandi</b>", ""]
    for r in rows:
        icon = config.KIND_ICONS[r["turi"]]
        note = r.get("izoh") or r["kategoriya"]
        lines.append(f"{icon} {fmt_money(r['summa'])} · {esc(note)}")
    return "\n".join(lines)
