# Serverga joylashtirish

Bot 24/7 ishlashi uchun Linux (Ubuntu/Debian) serverga `systemd` xizmati
sifatida o'rnatiladi.

## Tez yo'l

Serverga SSH orqali kiring va bitta buyruq bilan o'rnating:

```bash
ssh root@SERVER_IP

curl -fsSL https://raw.githubusercontent.com/NodirbekIskandarov/tangam/main/deploy/setup.sh \
  -o setup.sh
bash setup.sh https://github.com/NodirbekIskandarov/tangam.git
```

Skript quyidagilarni bajaradi:

1. `python3`, `venv`, `git` paketlarini o'rnatadi
2. `tanga` nomli tizim foydalanuvchisini yaratadi (bot root sifatida ishlamaydi)
3. Loyihani `/opt/tanga` ga klonlaydi
4. Virtual muhit yaratib bog'liqliklarni o'rnatadi
5. `.env` faylini `.env.example` dan nusxalaydi (huquqlari `600`)
6. `systemd` xizmatini yoqadi

Keyin `.env` ni to'ldirasiz va xizmatni ishga tushirasiz:

```bash
nano /opt/tanga/.env      # TELEGRAM_TOKEN, ANTHROPIC_API_KEY, ALLOWED_USER_IDS
systemctl start tanga
journalctl -u tanga -f    # loglarni kuzatish
```

> ⚠️ **Bir vaqtning o'zida bitta nusxa ishlashi kerak.** Telegram bitta tokenga
> faqat bitta `getUpdates` oqimini beradi. Serverda ishga tushirishdan oldin
> kompyuteringizdagi botni to'xtating, aks holda ikkalasi ham xabarlarni
> o'g'irlab, uzilib-uzilib ishlaydi.

## Yangilanishni chiqarish

Kodni o'zgartirib GitHub'ga yuborganingizdan keyin, serverda:

```bash
cd /opt/tanga
git pull
.venv/bin/pip install -q -r requirements.txt
systemctl restart tanga
```

Yoki shunchaki `setup.sh` ni qayta ishga tushiring — u mavjud `.env` va
bazaga tegmaydi.

## Foydali buyruqlar

| Buyruq | Vazifasi |
|---|---|
| `systemctl status tanga` | Holati |
| `systemctl restart tanga` | Qayta ishga tushirish |
| `systemctl stop tanga` | To'xtatish |
| `journalctl -u tanga -f` | Loglarni jonli kuzatish |
| `journalctl -u tanga --since "1 hour ago"` | Oxirgi 1 soatlik loglar |

## Bazani zaxiralash

Baza — oddiy fayl: `/opt/tanga/tanga.db`.

```bash
# Qo'lda nusxa olish
cp /opt/tanga/tanga.db /root/tanga-$(date +%F).db

# Har kuni avtomatik (crontab -e)
0 3 * * * cp /opt/tanga/tanga.db /root/backup/tanga-$(date +\%F).db
```

Kompyuterga tortib olish:

```bash
scp root@SERVER_IP:/opt/tanga/tanga.db ./
```

## Xavfsizlik

- `.env` git'ga **hech qachon** yuborilmaydi (`.gitignore` da).
  Serverda uning huquqlari `600` — faqat egasi o'qiy oladi.
- Bot `root` sifatida emas, alohida `tanga` foydalanuvchisi ostida ishlaydi.
- `systemd` unitida `ProtectSystem=strict` va `NoNewPrivileges=true` yoqilgan —
  bot faqat o'z papkasiga yoza oladi.
- Serverga parol bilan emas, **SSH kalit** bilan kirishni yoqing va parol
  orqali kirishni o'chiring:

```bash
# Kompyuteringizda (bir marta)
ssh-keygen -t ed25519
ssh-copy-id root@SERVER_IP

# Serverda: /etc/ssh/sshd_config
#   PasswordAuthentication no
systemctl restart ssh
```

## Muammolarni bartaraf qilish

**Bot ishga tushmayapti**

```bash
journalctl -u tanga -n 50 --no-pager
```

- `.env faylida quyidagilar yo'q: ...` → `.env` to'ldirilmagan
- `Conflict: terminated by other getUpdates` → bot boshqa joyda ham ishlayapti
- `authentication_error` → `ANTHROPIC_API_KEY` noto'g'ri yoki bekor qilingan

**Vaqt mintaqasi noto'g'ri**

`.env` dagi `TIMEZONE=Asia/Tashkent` hisobotlar uchun ishlatiladi; serverning
o'z vaqti boshqa bo'lsa ham bot shu mintaqada hisoblaydi.
