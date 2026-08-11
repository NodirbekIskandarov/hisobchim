"""Oylik hisobotni ulashsa bo'ladigan rasmga aylantiradi.

Maqsad — foydalanuvchi o'z natijasini do'stlariga ko'rsatsin. Rasm pastida
bot nomi turadi, ya'ni har bir ulashish bepul reklama bo'ladi.

Pillow yoki shrift topilmasa — None qaytaradi, chaqiruvchi matnli
hisobotga qaytadi. Rasm yo'qligi xato emas.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import config

log = logging.getLogger("hisobchi.sharecard")

W, H = 1080, 1350          # Telegram va Instagram uchun qulay nisbat (4:5)

# Ranglar — Mini App palitrasi bilan bir xil oila.
BG_TOP = (16, 22, 34)
BG_BOTTOM = (28, 38, 56)
INK = (238, 242, 248)
INK_2 = (150, 165, 187)
ACCENT = (86, 170, 232)
GOOD = (95, 200, 140)
BAD = (240, 130, 118)
CARD = (26, 35, 51)

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
]
BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _find(candidates: list[str]) -> str | None:
    for path in candidates:
        if Path(path).exists():
            return path
    return None


def available() -> bool:
    try:
        import PIL  # noqa: F401
    except ImportError:
        return False
    return _find(FONT_CANDIDATES) is not None


def _money(value: float, currency: str = "som") -> str:
    """Rasmda joy kam — katta sonlarni qisqartiramiz."""
    if currency == "usd":
        return f"${value:,.2f}".replace(",", " ")
    v = abs(value)
    if v >= 1_000_000:
        text = f"{value / 1_000_000:.1f} mln".replace(".0 ", " ")
    elif v >= 1_000:
        text = f"{value / 1_000:.0f} ming"
    else:
        text = f"{value:.0f}"
    return f"{text} so'm"


def build(*, title: str, kirim: float, chiqim: float, categories: list[tuple],
          currency: str = "som", entries: int = 0,
          bot_username: str = "") -> bytes | None:
    """Oylik natijani PNG qilib qaytaradi. Muvaffaqiyatsiz bo'lsa None."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        log.info("Pillow yo'q — ulashish rasmi tayyorlanmadi")
        return None

    regular_path = _find(FONT_CANDIDATES)
    bold_path = _find(BOLD_CANDIDATES) or regular_path
    if not regular_path:
        log.info("Shrift topilmadi — ulashish rasmi tayyorlanmadi")
        return None

    def font(size: int, bold: bool = False):
        return ImageFont.truetype(bold_path if bold else regular_path, size)

    img = Image.new("RGB", (W, H), BG_TOP)
    draw = ImageDraw.Draw(img)

    # Yumshoq vertikal gradient — tekis fon yassi ko'rinadi.
    for y in range(H):
        t = y / H
        draw.line(
            [(0, y), (W, y)],
            fill=tuple(int(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)))

    pad = 72
    y = 96

    draw.text((pad, y), "MOLIYAVIY HISOBOT", font=font(30, True), fill=ACCENT)
    y += 52
    draw.text((pad, y), title, font=font(66, True), fill=INK)
    y += 108

    # Kirim / chiqim kartalari
    card_w = (W - pad * 2 - 28) // 2
    for i, (label, value, color) in enumerate(
            [("Kirim", kirim, GOOD), ("Chiqim", chiqim, BAD)]):
        x = pad + i * (card_w + 28)
        draw.rounded_rectangle([x, y, x + card_w, y + 168], radius=22, fill=CARD)
        draw.text((x + 30, y + 28), label.upper(), font=font(26, True), fill=INK_2)
        draw.text((x + 30, y + 74), _money(value, currency), font=font(44, True),
                  fill=color)
    y += 210

    # Farq
    diff = kirim - chiqim
    draw.rounded_rectangle([pad, y, W - pad, y + 132], radius=22, fill=CARD)
    draw.text((pad + 30, y + 26), "FARQ", font=font(26, True), fill=INK_2)
    draw.text((pad + 30, y + 66), _money(diff, currency), font=font(48, True),
              fill=GOOD if diff >= 0 else BAD)
    if entries:
        label = f"{entries} ta yozuv"
        box = draw.textbbox((0, 0), label, font=font(28))
        draw.text((W - pad - 30 - (box[2] - box[0]), y + 78), label,
                  font=font(28), fill=INK_2)
    y += 186

    # Kategoriyalar
    if categories:
        draw.text((pad, y), "ENG KO'P XARAJAT", font=font(28, True), fill=INK_2)
        y += 56
        biggest = max(amount for _, amount, *_ in categories[:5]) or 1
        for name, amount, *rest in categories[:5]:
            share = amount / biggest
            draw.text((pad, y), name.capitalize(), font=font(34), fill=INK)
            value_text = _money(amount, currency)
            box = draw.textbbox((0, 0), value_text, font=font(34, True))
            draw.text((W - pad - (box[2] - box[0]), y), value_text,
                      font=font(34, True), fill=INK)
            y += 50
            bar_w = int((W - pad * 2) * share)
            draw.rounded_rectangle([pad, y, W - pad, y + 16], radius=8, fill=CARD)
            if bar_w > 16:
                draw.rounded_rectangle([pad, y, pad + bar_w, y + 16], radius=8,
                                       fill=ACCENT)
            y += 52

    # Pastki qism — brend
    foot = H - 108
    draw.line([(pad, foot - 34), (W - pad, foot - 34)], fill=(52, 66, 88), width=2)
    draw.text((pad, foot), "Hisobchi AI", font=font(38, True), fill=INK)
    handle = f"@{bot_username}" if bot_username else "Telegram bot"
    box = draw.textbbox((0, 0), handle, font=font(32))
    draw.text((W - pad - (box[2] - box[0]), foot + 6), handle, font=font(32),
              fill=ACCENT)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
