#!/usr/bin/env bash
# Hisobchi botni Ubuntu/Debian serverga o'rnatadi.
# Serverda root sifatida ishga tushiring:
#   bash setup.sh https://github.com/NodirbekIskandarov/hisobchim.git
#
# Qayta-qayta ishga tushirish xavfsiz — mavjud .env va bazaga tegmaydi.

set -euo pipefail

REPO="${1:-https://github.com/NodirbekIskandarov/hisobchim.git}"
APP_DIR=/opt/hisobchi
APP_USER=hisobchi

if [[ $EUID -ne 0 ]]; then
  echo "Bu skriptni root sifatida ishga tushiring (sudo bash setup.sh)" >&2
  exit 1
fi

echo "==> Paketlar o'rnatilmoqda"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip git tzdata

echo "==> Foydalanuvchi: $APP_USER"
id -u "$APP_USER" &>/dev/null || useradd --system --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$APP_USER"

echo "==> Kod: $APP_DIR"
if [[ -d "$APP_DIR/.git" ]]; then
  git -C "$APP_DIR" fetch --all -q
  git -C "$APP_DIR" reset --hard origin/main -q
else
  mkdir -p "$APP_DIR"
  git clone -q "$REPO" "$APP_DIR"
fi

echo "==> Python muhiti"
if [[ ! -d "$APP_DIR/.venv" ]]; then
  python3 -m venv "$APP_DIR/.venv"
fi
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$APP_DIR/.venv/bin/pip" install --quiet -r "$APP_DIR/requirements.txt"

echo "==> Sozlamalar fayli"
if [[ ! -f "$APP_DIR/.env" ]]; then
  cp "$APP_DIR/.env.example" "$APP_DIR/.env"
  chmod 600 "$APP_DIR/.env"
  echo
  echo "  ⚠️  $APP_DIR/.env yaratildi, lekin TO'LDIRILMAGAN."
  echo "     Quyidagilarni yozing va keyin xizmatni qayta ishga tushiring:"
  echo "       TELEGRAM_TOKEN, ANTHROPIC_API_KEY, ALLOWED_USER_IDS"
  echo
  NEEDS_ENV=1
else
  echo "     .env allaqachon mavjud — tegilmadi."
  NEEDS_ENV=0
fi

chown -R "$APP_USER:$APP_USER" "$APP_DIR"
chmod 600 "$APP_DIR/.env"

echo "==> systemd xizmati"
cp "$APP_DIR/deploy/hisobchi.service" /etc/systemd/system/hisobchi.service
systemctl daemon-reload
systemctl enable hisobchi -q

if [[ "$NEEDS_ENV" -eq 1 ]]; then
  echo
  echo "O'rnatish tugadi, lekin bot ISHGA TUSHIRILMADI — avval .env ni to'ldiring:"
  echo "   nano $APP_DIR/.env"
  echo "   systemctl start hisobchi"
else
  systemctl restart hisobchi
  sleep 2
  systemctl --no-pager --lines=15 status hisobchi || true
fi

echo
echo "Loglar:      journalctl -u hisobchi -f"
echo "Qayta ishga: systemctl restart hisobchi"
echo "To'xtatish:  systemctl stop hisobchi"
