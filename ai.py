"""Anthropic API bilan ishlash: erkin matnni moliyaviy yozuvga aylantirish
va foydalanuvchi savollariga uning ma'lumotlari asosida javob berish."""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

from anthropic import AsyncAnthropic

import config

log = logging.getLogger(__name__)

_client: AsyncAnthropic | None = None


def client() -> AsyncAnthropic:
    global _client
    if _client is None:
        _client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


# --------------------------------------------------------------------------- #
# 1-vazifa: matnni yozuvlarga ajratish
# --------------------------------------------------------------------------- #

RECORD_TOOL = {
    "name": "yozuvlarni_qaytar",
    "description": (
        "Foydalanuvchi xabaridan ajratib olingan moliyaviy yozuvlarni qaytaradi. "
        "Har doim shu asbobdan foydalan."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "niyat": {
                "type": "string",
                "enum": ["yozuv", "savol", "tushunarsiz"],
                "description": (
                    "'yozuv' — xabarda kirim/chiqim/qarz qayd etilgan. "
                    "'savol' — foydalanuvchi o'z moliyasi haqida so'ramoqda "
                    "(masalan: bu oy qancha sarfladim). "
                    "'tushunarsiz' — moliyaga aloqasi yo'q yoki summa aniqlanmadi."
                ),
            },
            "yozuvlar": {
                "type": "array",
                "description": "Xabardagi har bir alohida amaliyot uchun bitta element.",
                "items": {
                    "type": "object",
                    "properties": {
                        "turi": {
                            "type": "string",
                            "enum": config.KINDS,
                            "description": (
                                "chiqim — pul sarflandi; kirim — pul kelib tushdi; "
                                "qarz_berdim — men birovga qarz berdim; "
                                "qarz_oldim — men birovdan qarz oldim."
                            ),
                        },
                        "summa": {
                            "type": "number",
                            "description": "Musbat son, valyuta birligisiz (masalan 50000).",
                        },
                        "valyuta": {
                            "type": "string",
                            "enum": config.SUPPORTED_CURRENCIES,
                            "description": (
                                "Xabarda \"$\", \"dollar\", \"USD\" kabi ishoralar bo'lsa "
                                "'usd', aks holda har doim 'som'."
                            ),
                        },
                        "kategoriya": {
                            "type": "string",
                            "enum": config.ALL_CATEGORIES,
                            "description": "Turiga mos kategoriya. Qarz uchun har doim 'qarz'.",
                        },
                        "izoh": {
                            "type": "string",
                            "description": (
                                "Qisqa izoh, 1-4 so'z, o'zbek tilida. Masalan: 'tushlik'. "
                                "Qarz uchun sababni yoz agar aytilgan bo'lsa (masalan "
                                "'uy uchun', 'mashina taʼmiri') — shaxs ismini takrorlama, "
                                "sabab aytilmagan bo'lsa 'qarz' deb qo'y."
                            ),
                        },
                        "shaxs": {
                            "type": "string",
                            "description": "Faqat qarz uchun: kimga/kimdan. Aks holda bo'sh qoldir.",
                        },
                        "sana": {
                            "type": "string",
                            "description": (
                                "YYYY-MM-DD formatida. Xabarda sana aytilmagan bo'lsa "
                                "bugungi sanani qo'y."
                            ),
                        },
                    },
                    "required": ["turi", "summa", "valyuta", "kategoriya", "izoh", "sana"],
                },
            },
            "izoh_matni": {
                "type": "string",
                "description": (
                    "Agar niyat 'tushunarsiz' bo'lsa — foydalanuvchiga o'zbekcha qisqa "
                    "tushuntirish. Aks holda bo'sh."
                ),
            },
        },
        "required": ["niyat", "yozuvlar"],
    },
}


def _parse_system_prompt(today: date) -> str:
    thousands_rule = (
        "- Birliksiz kichik son (1000 dan kichik) odatda mingni bildiradi, "
        "LEKIN FAQAT SO'M UCHUN: \"obedga 50\" => 50000 som, \"taksi 20\" => "
        "20000 som. Dollar summasiga bu qoida qo'llanmaydi (pastga qarang).\n"
        if config.SMALL_NUMBERS_ARE_THOUSANDS
        else "- Sonlarni aynan yozilganidek ol, o'zingdan ko'paytirma.\n"
    )
    return (
        "Sen o'zbek tilidagi shaxsiy moliya botining tahlil qismisan. "
        "Foydalanuvchining erkin yozilgan xabarini o'qib, undan kirim, chiqim va "
        "qarz yozuvlarini ajratib olasan.\n\n"
        f"Bugungi sana: {today.isoformat()}.\n"
        f"Standart valyuta: {config.CURRENCY} ('som'). Ikkinchi qo'llab-quvvatlanadigan "
        "valyuta: AQSH dollari ('usd').\n\n"
        "Qoidalar:\n"
        "- Har doim yozuvlarni_qaytar asbobini chaqir, oddiy matn bilan javob berma.\n"
        "- Bitta xabarda bir nechta amaliyot bo'lishi mumkin — har birini alohida "
        "element qilib qaytar. Masalan: \"obed 40 ming, taksi 20 ming\" => 2 ta yozuv.\n"
        "- Summani raqamga aylantir: \"ming\"/\"k\" = 1000, \"mln\"/\"million\"/\"lim\" = 1000000. "
        "\"250 ming\" => 250000, \"1.5 mln\" => 1500000.\n"
        + thousands_rule
        + "- Bo'sh joy yoki nuqta bilan ajratilgan raqamlarni to'g'ri o'qi: "
        "\"1 200 000\" => 1200000.\n"
        "- VALYUTANI ANIQLASH: agar summa oldida/yonida \"$\", \"dollar\", "
        "\"dollarda\", \"USD\" so'zlari bo'lsa => valyuta=\"usd\" va sonni "
        "AYNAN YOZILGANIDEK ol, ming qoidasini QO'LLAMA — \"$100\" => 100 (usd), "
        "\"50 dollar\" => 50 (usd), \"200 dollar oylik berdim\" => 200 (usd). "
        "Aks holda valyuta=\"som\" va yuqoridagi ming/million qoidalari amal qiladi.\n"
        "- Turini PUL OQIMI YO'NALISHIGA qarab aniqla, alohida fe'lga qarab emas — "
        "butun jumla mazmunini o'qi. Savolni shunday qo'y: pul SIZDAN chiqyaptimi "
        "yoki SIZGA kelyaptimi?\n"
        "  * Pul sizdan chiqsa (xarid, to'lov, xizmat haqi, sarf) => chiqim.\n"
        "  * Pul sizga kelsa (maosh, sotuv, qaytim, sovg'a, qarz qaytishi) => kirim.\n"
        "- OGOHLANTIRISH — bir xil fe'l ikki xil ma'noda kelishi mumkin, faqat "
        "fe'lning o'ziga qarab xulosa chiqarma:\n"
        "  * \"oldim\": \"noutbuk sotib oldim\" => chiqim (xarid), lekin "
        "\"do'stimdan 200 ming oldim\", \"maoshimni oldim\" => kirim (pul qabul qildi).\n"
        "  * \"berdim\": \"kira haqini berdim\" => chiqim (to'lov), lekin "
        "\"tovarni sotib berdim\" => kirim (sotuvdan tushum). \"Aliga 500 ming "
        "qarz berdim\" => qarz_berdim (qarz so'zi aniq aytilgan bo'lsagina).\n"
        "  * \"tushdi\": \"oylik tushdi\", \"pul tushdi\" => kirim. Narx/kurs "
        "pasayishi haqida bo'lsa (\"narxi tushdi\") — moliyaviy yozuv emas.\n"
        "- Aniq kirim belgilari: \"oylik\", \"maosh\", \"daromad\", \"kirdi\", "
        "\"tushdi\" (pul ma'nosida), \"sotdim\", \"ishladim\", \"pul yubordi/keldi\", "
        "\"qaytim\", \"sovg'a berishdi\".\n"
        "- Aniq chiqim belgilari: \"sotib oldim\", \"xarid qildim\", \"to'ladim\", "
        "\"sarfladim\", xizmat/mahsulot nomlari ega gaplar (\"taksi\", \"obed\", "
        "\"kommunal\", \"kira\") — bularda pul deyarli har doim sizdan chiqadi.\n"
        "- Misollar: \"telefon sotib oldim 2 mln\" => chiqim. \"telefonni sotdim "
        "2 mln\" => kirim. \"do'stimdan 500 ming oldim\" => kirim. \"ish haqim "
        "tushdi\" => kirim. \"kira puli to'ladim\" => chiqim.\n"
        "- \"Aliga 500 ming qarz berdim\" => qarz_berdim, shaxs=\"Ali\". "
        "\"Akamdan 1 mln qarz oldim\" => qarz_oldim, shaxs=\"akam\". Qarz turi "
        "faqat \"qarz\" so'zi yoki uning aniq ma'nosi (masalan \"nasiya\") "
        "jumlada bo'lsa qo'llanadi — aks holda oddiy kirim/chiqim.\n"
        "- \"kecha\", \"ertalab\", \"1-avgustda\" kabi vaqt ko'rsatkichlarini sanaga aylantir. "
        "Vaqt aytilmasa bugungi sana.\n"
        "- Kategoriyani faqat ro'yxatdagilardan tanla. Mahsulot/xizmatning "
        "MAZMUNIGA qarab tanla, sirtqi so'zga emas: \"dorixona\", \"shifokor\" "
        "=> salomatlik (oziq-ovqat emas). \"internet\", \"mobil aloqa\" => "
        "aloqa va internet (xizmatlar emas). \"kira haqi\", \"ijaraga\" => "
        "uy-joy. \"svet\", \"gaz\", \"suv\" (kommunal to'lov ma'nosida) => "
        "kommunal. Ishonching komil bo'lmasa \"boshqa chiqim\" yoki "
        "\"boshqa kirim\" qo'y — noto'g'ri kategoriyadan ko'ra shu yaxshi.\n"
        "- Agar xabar savol bo'lsa (masalan \"bu oy qancha sarfladim?\", "
        "\"eng ko'p nimaga ketdi?\") — niyat=\"savol\", yozuvlar bo'sh massiv.\n"
        "- Agar summa umuman yo'q yoki matn moliyaga aloqador bo'lmasa — "
        "niyat=\"tushunarsiz\" va izoh_matni'da qisqa tushuntirish yoz.\n"
    )


def _coerce_date(raw: Any, today: date) -> str:
    if isinstance(raw, str) and len(raw) == 10:
        try:
            return date.fromisoformat(raw).isoformat()
        except ValueError:
            pass
    return today.isoformat()


async def parse_message(text: str, today: date | None = None) -> dict[str, Any]:
    """Xabarni tahlil qiladi.

    Qaytaradi: {"niyat": str, "yozuvlar": [ ... ], "izoh_matni": str}
    """
    today = today or date.today()

    resp = await client().messages.create(
        model=config.PARSE_MODEL,
        max_tokens=1500,
        system=_parse_system_prompt(today),
        tools=[RECORD_TOOL],
        tool_choice={"type": "tool", "name": "yozuvlarni_qaytar"},
        messages=[{"role": "user", "content": text}],
    )

    payload: dict[str, Any] | None = None
    for block in resp.content:
        if block.type == "tool_use" and block.name == "yozuvlarni_qaytar":
            payload = block.input
            break

    if not payload:
        log.warning("Model asbobni chaqirmadi: %s", resp.content)
        return {"niyat": "tushunarsiz", "yozuvlar": [], "izoh_matni": ""}

    niyat = payload.get("niyat", "tushunarsiz")
    cleaned: list[dict[str, Any]] = []

    for item in payload.get("yozuvlar") or []:
        try:
            amount = float(item.get("summa", 0))
        except (TypeError, ValueError):
            continue
        if amount <= 0:
            continue

        kind = item.get("turi")
        if kind not in config.KINDS:
            kind = config.KIND_CHIQIM

        person = (item.get("shaxs") or "").strip() or None
        if kind not in config.DEBT_KINDS:
            person = None

        cleaned.append(
            {
                "turi": kind,
                "summa": round(amount, 2),
                "valyuta": config.normalize_currency(item.get("valyuta")),
                "kategoriya": config.normalize_category(kind, item.get("kategoriya")),
                "izoh": (item.get("izoh") or "").strip()[:120],
                "shaxs": person,
                "sana": _coerce_date(item.get("sana"), today),
            }
        )

    if cleaned:
        niyat = "yozuv"
    elif niyat == "yozuv":
        niyat = "tushunarsiz"

    return {
        "niyat": niyat,
        "yozuvlar": cleaned,
        "izoh_matni": (payload.get("izoh_matni") or "").strip(),
    }


# --------------------------------------------------------------------------- #
# 2-vazifa: chek rasmini o'qish
# --------------------------------------------------------------------------- #

RECEIPT_TOOL = {
    "name": "chekni_qaytar",
    "description": (
        "Chek (kvitansiya) rasmidan do'kon, sana va mahsulotlar ro'yxatini qaytaradi. "
        "Har doim shu asbobdan foydalan."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "oqildi": {
                "type": "boolean",
                "description": (
                    "Rasmda chek bor va hech bo'lmasa bitta mahsulot qatori o'qilgan "
                    "bo'lsa true. Rasm chek bo'lmasa yoki umuman o'qib bo'lmasa false."
                ),
            },
            "dokon": {
                "type": "string",
                "description": "Do'kon/tashkilot nomi. Ko'rinmasa bo'sh qoldir.",
            },
            "sana": {
                "type": "string",
                "description": (
                    "Chekda yozilgan sana, YYYY-MM-DD formatida. "
                    "Chekda sana ko'rinmasa bugungi sanani qo'y."
                ),
            },
            "mahsulotlar": {
                "type": "array",
                "description": (
                    "Chekdagi har bir mahsulot qatori uchun bitta element. "
                    "Jami/ITOGO/chegirma/QQS kabi yakuniy qatorlarni bu ro'yxatga QO'SHMA."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "nomi": {
                            "type": "string",
                            "description": "Mahsulot nomi chekda yozilganidek.",
                        },
                        "miqdori": {
                            "type": "number",
                            "description": "Soni yoki og'irligi. Ko'rsatilmagan bo'lsa 1.",
                        },
                        "birlik_narxi": {
                            "type": "number",
                            "description": "Bir dona/kg narxi. Ko'rinmasa qo'shma.",
                        },
                        "summa": {
                            "type": "number",
                            "description": (
                                "Shu qator uchun yakuniy summa (miqdor x narx), "
                                "valyuta birligisiz musbat son."
                            ),
                        },
                        "kategoriya": {
                            "type": "string",
                            "enum": config.EXPENSE_CATEGORIES,
                            "description": "Mahsulotga eng mos keladigan kategoriya.",
                        },
                    },
                    "required": ["nomi", "summa", "kategoriya"],
                },
            },
            "chekdagi_jami": {
                "type": "number",
                "description": (
                    "Chekda 'JAMI'/'ITOGO'/'TO'LANDI' deb yozilgan yakuniy summa. "
                    "Ko'rinmasa bu maydonni qo'shma."
                ),
            },
            "chegirma": {
                "type": "number",
                "description": "Chegirma/skidka summasi, agar ko'rsatilgan bo'lsa.",
            },
            "izoh_matni": {
                "type": "string",
                "description": (
                    "oqildi=false bo'lsa — nima uchun o'qib bo'lmaganini o'zbekcha "
                    "qisqa tushuntir. Aks holda bo'sh."
                ),
            },
        },
        "required": ["oqildi", "mahsulotlar"],
    },
}


def _receipt_system_prompt(today: date, parts: int) -> str:
    multi = (
        (
            f"\nMUHIM: sizga bitta uzun chekning {parts} ta rasmi berilgan "
            "(chek kameraga sig'magani uchun qismlarga bo'lingan). Ular yuqoridan "
            "pastga ketma-ket. Hammasini BITTA chek deb hisobla.\n"
            "- Qismlar bir-birini qisman takrorlashi mumkin (bir xil qator ikkita "
            "rasmda ko'rinishi mumkin). Takrorlangan qatorni FAQAT BIR MARTA yoz.\n"
            "- Qator ikki rasm chegarasida bo'linib qolgan bo'lsa, uni to'liq "
            "ko'ringan joyidan ol.\n"
            "- Do'kon nomi odatda 1-qismda, JAMI summa oxirgi qismda bo'ladi.\n"
        )
        if parts > 1
        else ""
    )
    return (
        "Sen o'zbek tilidagi shaxsiy moliya botining chek o'qish qismisan. "
        "Berilgan chekni (rasm yoki PDF) diqqat bilan o'qib, undagi mahsulotlar "
        "ro'yxatini ajratib ol.\n"
        "PDF bir necha sahifadan iborat bo'lsa, hammasi BITTA chek deb hisobla va "
        "barcha sahifalardagi mahsulotlarni bitta ro'yxatga yig'.\n\n"
        f"Bugungi sana: {today.isoformat()}.\n"
        f"Valyuta: {config.CURRENCY}.\n"
        + multi
        + "\nQoidalar:\n"
        "- Har doim chekni_qaytar asbobini chaqir, oddiy matn bilan javob berma.\n"
        "- Har bir mahsulot qatorini alohida element qil. Nomini chekda "
        "yozilganidek ko'chir, o'zingdan o'zgartirma.\n"
        "- Summalarni aynan chekdagidek ol. Sonlarni O'ZING QO'SHMA — jami "
        "summani dastur hisoblaydi. Sening vazifang faqat to'g'ri o'qish.\n"
        "- Bo'sh joy, nuqta yoki vergul bilan ajratilgan sonlarni to'g'ri o'qi: "
        "\"12 500\" => 12500, \"1.250,00\" => 1250.\n"
        "- 'JAMI', 'ITOGO', 'ВСЕГО', 'TO'LANDI', 'QQS', 'NDS', 'Naqd', 'Karta', "
        "'Qaytim' kabi qatorlar mahsulot EMAS — ularni mahsulotlar ro'yxatiga "
        "qo'shma. Yakuniy summani chekdagi_jami ga yoz.\n"
        "- Har bir mahsulotga ro'yxatdagi kategoriyalardan eng mosini tanla. "
        "Oziq-ovqat do'konidagi non, sut, go'sht => 'oziq-ovqat'. Kimyo, "
        "yuvish vositalari => 'xizmatlar' emas, 'boshqa chiqim'. Dori => "
        "'salomatlik'. Ishonching komil bo'lmasa 'boshqa chiqim' qo'y.\n"
        "- Chekda o'qilmaydigan qatorlar bo'lsa, o'qilganlarini qaytar — "
        "butun chekni tashlab yuborma.\n"
        "- Fayl chek bo'lmasa (masalan oddiy surat yoki boshqa hujjat) => "
        "oqildi=false va izoh_matni'da qisqa tushuntirish.\n"
    )


PDF_MEDIA_TYPE = "application/pdf"


def _receipt_content(
    images: list[tuple[str, str]], caption: str, note: str = ""
) -> list[dict[str, Any]]:
    """Rasm va PDF qismlaridan API uchun kontent bloklarini yig'adi."""
    content: list[dict[str, Any]] = []
    parts = len(images)
    for idx, (data, media_type) in enumerate(images, start=1):
        if parts > 1:
            content.append({"type": "text", "text": f"--- Chekning {idx}-qismi ---"})
        if media_type == PDF_MEDIA_TYPE:
            # PDF Claude'ga alohida "document" bloki sifatida beriladi; ichida
            # matn qatlami bo'lsa u to'g'ridan-to'g'ri o'qiladi (aniqroq),
            # skanerlangan bo'lsa sahifalar rasm sifatida ko'riladi.
            content.append(
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": PDF_MEDIA_TYPE,
                        "data": data,
                    },
                }
            )
        else:
            content.append(
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": data},
                }
            )

    tail = "Shu chekni o'qib, mahsulotlar ro'yxatini qaytar."
    if caption.strip():
        tail += f"\nFoydalanuvchi izohi: {caption.strip()}"
    if note:
        tail += f"\n\n{note}"
    content.append({"type": "text", "text": tail})
    return content


async def _receipt_call(
    images: list[tuple[str, str]],
    today: date,
    caption: str,
    note: str = "",
    force: bool = False,
) -> dict[str, Any] | None:
    kwargs: dict[str, Any] = {
        "model": config.VISION_MODEL,
        "max_tokens": 16000,
        "system": _receipt_system_prompt(today, len(images)),
        "tools": [RECEIPT_TOOL],
        "output_config": {"effort": "high"},
        "messages": [
            {"role": "user", "content": _receipt_content(images, caption, note)}
        ],
    }
    if force:
        # Majburiy asbob chaqiruvi "thinking" bilan birga ishlamaydi.
        kwargs["tool_choice"] = {"type": "tool", "name": "chekni_qaytar"}
        kwargs["thinking"] = {"type": "disabled"}
    else:
        # Aniqlik uchun model rasmni o'ylab o'qiydi.
        kwargs["thinking"] = {"type": "adaptive"}

    resp = await client().messages.create(**kwargs)
    for block in resp.content:
        if block.type == "tool_use" and block.name == "chekni_qaytar":
            return block.input
    return None


def _normalize_receipt(payload: dict[str, Any], today: date) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for raw in payload.get("mahsulotlar") or []:
        try:
            amount = float(raw.get("summa", 0))
        except (TypeError, ValueError):
            continue
        if amount <= 0:
            continue

        try:
            qty = raw.get("miqdori")
            qty = float(qty) if qty is not None else None
        except (TypeError, ValueError):
            qty = None

        items.append(
            {
                "nomi": (raw.get("nomi") or "").strip()[:120] or "nomsiz",
                "miqdori": qty,
                "summa": round(amount, 2),
                "kategoriya": config.normalize_category(
                    config.KIND_CHIQIM, raw.get("kategoriya")
                ),
            }
        )

    def _num(key: str) -> float | None:
        try:
            value = float(payload[key])
        except (KeyError, TypeError, ValueError):
            return None
        return value if value > 0 else None

    return {
        "oqildi": bool(payload.get("oqildi")) and bool(items),
        "dokon": (payload.get("dokon") or "").strip()[:80],
        "sana": _coerce_date(payload.get("sana"), today),
        "mahsulotlar": items,
        "chekdagi_jami": _num("chekdagi_jami"),
        "chegirma": _num("chegirma"),
        "izoh_matni": (payload.get("izoh_matni") or "").strip(),
    }


def receipt_check(data: dict[str, Any]) -> dict[str, Any]:
    """Chekni tekshiradi: mahsulotlar yig'indisini Python hisoblab, chekdagi
    JAMI bilan solishtiradi. Arifmetika AI'ga ishonib topshirilmaydi."""
    computed = round(sum(item["summa"] for item in data["mahsulotlar"]), 2)
    discount = data.get("chegirma") or 0.0
    printed = data.get("chekdagi_jami")

    expected = round(computed - discount, 2)
    if printed is None:
        return {"holat": "jami_yoq", "hisoblangan": computed,
                "chekdagi": None, "farq": None}

    diff = round(expected - printed, 2)
    # Yaxlitlash xatosi uchun kichik bag'rikenglik.
    tolerance = max(1.0, abs(printed) * 0.001)
    holat = "mos" if abs(diff) <= tolerance else "farqli"
    return {"holat": holat, "hisoblangan": computed,
            "chekdagi": printed, "farq": diff}


async def parse_receipt(
    images: list[tuple[str, str]],
    today: date | None = None,
    caption: str = "",
) -> dict[str, Any]:
    """Chek rasm(lar)ini o'qiydi va tekshiradi.

    images: [(base64_data, media_type), ...] — uzun chek bo'lsa bir nechta qism.

    Aniqlik uchun ikki bosqich: agar mahsulotlar yig'indisi chekdagi JAMI bilan
    mos kelmasa, model rasmni farq haqida xabardor qilingan holda qayta o'qiydi.
    """
    today = today or date.today()

    payload = await _receipt_call(images, today, caption)
    if payload is None:
        # Model asbobni chaqirmadi — majburiy rejimda qayta urinamiz.
        log.warning("Chek: model asbobni chaqirmadi, majburiy rejimga o'tildi")
        payload = await _receipt_call(images, today, caption, force=True)

    if payload is None:
        return {
            "oqildi": False, "dokon": "", "sana": today.isoformat(),
            "mahsulotlar": [], "chekdagi_jami": None, "chegirma": None,
            "izoh_matni": "Chekni o'qib bo'lmadi. Yorug'roq va aniqroq surat yuboring.",
            "tekshiruv": {"holat": "jami_yoq", "hisoblangan": 0.0,
                          "chekdagi": None, "farq": None},
        }

    data = _normalize_receipt(payload, today)
    check = receipt_check(data)

    # Tekshiruv: yig'indi chekdagi JAMI bilan mos kelmasa — qayta o'qish.
    if data["oqildi"] and check["holat"] == "farqli":
        log.info(
            "Chek nomuvofiqligi: hisoblangan=%s chekdagi=%s farq=%s — qayta o'qilmoqda",
            check["hisoblangan"], check["chekdagi"], check["farq"],
        )
        missing = -check["farq"]
        note = (
            "DIQQAT — tekshiruv xatosi topildi. Sen o'qigan mahsulotlar yig'indisi "
            f"{check['hisoblangan']:.0f}, lekin chekdagi JAMI {check['chekdagi']:.0f}. "
            f"Farq: {abs(check['farq']):.0f}.\n"
            + (
                "Yig'indi JAMI'dan KICHIK — demak bir yoki bir nechta qator "
                "tushib qolgan, yoki summa kam o'qilgan.\n"
                if missing > 0
                else "Yig'indi JAMI'dan KATTA — demak biror qator ikki marta "
                "yozilgan (qismlar takrorlanishi mumkin), yoki summa ortiq "
                "o'qilgan, yoki JAMI emas boshqa qator olingan.\n"
            )
            + "Rasmni QAYTADAN, qator-baqator diqqat bilan o'qi va to'g'rilangan "
            "to'liq ro'yxatni qaytar. Har bir raqamni chekdagi bilan solishtir."
        )
        retry = await _receipt_call(images, today, caption, note=note)
        if retry is not None:
            data2 = _normalize_receipt(retry, today)
            check2 = receipt_check(data2)
            # Faqat yaxshiroq bo'lsa almashtiramiz.
            if data2["oqildi"] and (
                check2["holat"] == "mos"
                or (
                    check2["farq"] is not None
                    and check["farq"] is not None
                    and abs(check2["farq"]) < abs(check["farq"])
                )
            ):
                data, check = data2, check2

    data["tekshiruv"] = check
    return data


# --------------------------------------------------------------------------- #
# 3-vazifa: ma'lumotlar asosida savolga javob
# --------------------------------------------------------------------------- #

QA_SYSTEM = (
    "Sen foydalanuvchining shaxsiy moliyaviy yordamchisisan. Quyida uning "
    "yozuvlari JSON ko'rinishida beriladi. Faqat shu ma'lumotlarga tayanib, "
    "o'zbek tilida qisqa va aniq javob ber.\n"
    "- MUHIM: 'hisoblangan' bo'limida tayyor jamlanmalar berilgan — ular dastur "
    "tomonidan aniq hisoblangan. Savol shu jamlanmalar bilan javob berilsa, "
    "sonlarni O'ZING QAYTA QO'SHMA, tayyorini ol.\n"
    "- Faqat tayyor jamlanmada yo'q narsani hisoblashing kerak bo'lsa, "
    "qo'shishni bosqichma-bosqich va diqqat bilan bajar.\n"
    "- MUHIM: som va dollar summalarini HECH QACHON bir-biriga qo'shma yoki "
    "taqqoslama — kurs berilmagan, taxminiy konvertatsiya noto'g'ri javobga "
    "olib keladi. Agar foydalanuvchida ikkala valyutada ham yozuv bo'lsa, "
    "javobda ikkalasini ALOHIDA ko'rsat (masalan \"5 000 000 so'm va $200\").\n"
    "- Sonlarni o'qishga qulay yoz: 1 250 000 so'm yoki $250.\n"
    "- Ma'lumot yetarli bo'lmasa, buni ochiq ayt va nimasi yetishmayotganini tushuntir.\n"
    "- Javob 6 qatordan oshmasin. Ortiqcha muqaddima yozma.\n"
    "- Oddiy matn bilan yoz: markdown belgilari (**, *, #, `) ishlatma — "
    "ular foydalanuvchiga xuddi shundayligicha ko'rinadi.\n"
    "- So'ralmasa moliyaviy maslahat berma; so'ralsa ham bu professional "
    "investitsiya maslahati emasligini eslat."
)


def _rows_to_json(rows) -> str:
    data = [
        {
            "sana": r["occurred_on"],
            "turi": r["kind"],
            "summa": r["amount"],
            "valyuta": r["currency"] if "currency" in r.keys() else "som",
            "kategoriya": r["category"],
            "izoh": r["note"],
            "shaxs": r["person"],
        }
        for r in rows
    ]
    return json.dumps(data, ensure_ascii=False)


def _aggregate(rows) -> dict[str, Any]:
    """Jamlanmalarni Python hisoblaydi — AI arifmetikasiga tayanmaslik uchun.

    Valyutalar ALOHIDA jamlanadi (som va usd birlashtirilmaydi — kurs yo'q,
    aralashtirish noto'g'ri jamiga olib keladi)."""
    per_currency: dict[str, dict[str, Any]] = {}

    for r in rows:
        cur = r["currency"] if "currency" in r.keys() else "som"
        bucket = per_currency.setdefault(cur, {
            "by_kind": {}, "by_category": {}, "by_day": {}, "count_by_category": {},
        })
        kind, amount = r["kind"], float(r["amount"])
        bucket["by_kind"][kind] = round(bucket["by_kind"].get(kind, 0.0) + amount, 2)
        if kind == config.KIND_CHIQIM:
            cat = r["category"]
            bucket["by_category"][cat] = round(bucket["by_category"].get(cat, 0.0) + amount, 2)
            bucket["count_by_category"][cat] = bucket["count_by_category"].get(cat, 0) + 1
            day = r["occurred_on"]
            bucket["by_day"][day] = round(bucket["by_day"].get(day, 0.0) + amount, 2)

    valyutalar_boyicha = {
        cur: {
            "turlar_boyicha_jami": b["by_kind"],
            "chiqim_kategoriyalari_boyicha_jami": dict(
                sorted(b["by_category"].items(), key=lambda kv: kv[1], reverse=True)
            ),
            "chiqim_kategoriyalari_boyicha_soni": b["count_by_category"],
            "kunlar_boyicha_chiqim": dict(sorted(b["by_day"].items())),
        }
        for cur, b in per_currency.items()
    }

    dates = [r["occurred_on"] for r in rows]
    return {
        "yozuvlar_soni": len(rows),
        "davr": {"boshi": min(dates), "oxiri": max(dates)} if dates else None,
        "valyutalar_boyicha": valyutalar_boyicha,
    }


async def answer_question(question: str, rows, today: date | None = None) -> str:
    today = today or date.today()
    if not rows:
        return "Hozircha bazada yozuv yo'q. Avval bir nechta xarajat yozing."

    content = (
        f"Bugungi sana: {today.isoformat()}\n"
        f"Valyutalar: som ({config.CURRENCY}) va usd ($) — alohida-alohida.\n\n"
        f"Tayyor jamlanmalar (dastur aniq hisoblagan):\n"
        f"{json.dumps(_aggregate(rows), ensure_ascii=False, indent=1)}\n\n"
        f"Yozuvlar (JSON):\n{_rows_to_json(rows)}\n\n"
        f"Savol: {question}"
    )

    # Sonnet 5'da adaptiv "thinking" sukut bo'yicha yoqilgan va max_tokens
    # o'ylash + javobni birgalikda cheklaydi — shuning uchun chegara keng.
    # Javob uzunligi QA_SYSTEM bilan cheklanadi (6 qator).
    resp = await client().messages.create(
        model=config.CHAT_MODEL,
        max_tokens=6000,
        output_config={"effort": "high"},
        system=QA_SYSTEM,
        messages=[{"role": "user", "content": content}],
    )

    parts = [b.text for b in resp.content if b.type == "text"]
    return "\n".join(parts).strip() or "Javob tayyorlab bo'lmadi, qaytadan urinib ko'ring."
