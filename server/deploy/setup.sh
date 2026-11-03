#!/usr/bin/env bash
# One-time setup of a fresh Vultr Ubuntu 24.04 server for the hallux valgus API.
#
#   ssh root@<IP> "mkdir -p /root/hv-src"
#   scp -r server/hv_server server/deploy server/manage.py server/requirements.txt server/.env.example root@<IP>:/root/hv-src/
#   ssh root@<IP> "bash /root/hv-src/deploy/setup.sh hv.example.co.kr admin@example.com"
#
# Installs PostgreSQL + nginx + Python, creates the hv database/user, deploys the
# app to /opt/hv-server, enables https (Let's Encrypt), firewall, daily backups.
set -euo pipefail

DOMAIN="${1:?usage: setup.sh <domain> [email-for-letsencrypt]}"
EMAIL="${2:-}"
SRC="$(cd "$(dirname "$0")/.." && pwd)"
APP=/opt/hv-server
DATA=/var/lib/hv-server

echo "== swap (2GB, for 1GB-RAM plans)"
if [ ! -f /swapfile ]; then
  fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile
  echo "/swapfile none swap sw 0 0" >> /etc/fstab
  sysctl -w vm.swappiness=10 && echo "vm.swappiness=10" > /etc/sysctl.d/99-swappiness.conf
fi

echo "== packages"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -yq postgresql nginx python3-venv certbot python3-certbot-nginx ufw unattended-upgrades

echo "== service user & folders"
id hv >/dev/null 2>&1 || useradd --system --home "$APP" --shell /usr/sbin/nologin hv
mkdir -p "$APP" "$DATA/xray" /var/backups/hv
cp -r "$SRC/hv_server" "$SRC/manage.py" "$SRC/requirements.txt" "$APP/"
chown -R hv:hv "$DATA"
chmod 750 "$DATA"

echo "== database"
if [ ! -f "$APP/.env" ]; then
  DB_PASS="$(openssl rand -base64 24 | tr -d '/+=')"
  sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
CREATE ROLE hv LOGIN PASSWORD '$DB_PASS';
CREATE DATABASE hv OWNER hv;
SQL
  sed "s|postgresql://hv:CHANGE_ME@127.0.0.1:5432/hv|postgresql://hv:${DB_PASS}@127.0.0.1:5432/hv|" \
    "$SRC/.env.example" > "$APP/.env"
  echo "   created $APP/.env (fill in ALIMTALK_* and REPORT_BASE_URL later)"
fi
chown root:hv "$APP/.env"
chmod 640 "$APP/.env"

echo "== python env"
python3 -m venv "$APP/.venv"
"$APP/.venv/bin/pip" install -q --upgrade pip
"$APP/.venv/bin/pip" install -q -r "$APP/requirements.txt"
(cd "$APP" && sudo -u hv "$APP/.venv/bin/python" manage.py init-db)

echo "== systemd"
cp "$SRC/deploy/hv-server.service" /etc/systemd/system/hv-server.service
systemctl daemon-reload
systemctl enable --now hv-server

echo "== firewall (ssh, http, https only) — before certbot, which needs port 80"
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable

echo "== nginx + https"
sed "s/__DOMAIN__/$DOMAIN/g" "$SRC/deploy/nginx-hv.conf" > /etc/nginx/sites-available/hv
ln -sf /etc/nginx/sites-available/hv /etc/nginx/sites-enabled/hv
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx
if [ -n "$EMAIL" ]; then CERT_MAIL=(-m "$EMAIL"); else CERT_MAIL=(--register-unsafely-without-email); fi
certbot --nginx -d "$DOMAIN" "${CERT_MAIL[@]}" --agree-tos --non-interactive --redirect

echo "== daily backup 03:30 KST (server clock is UTC → 18:30 UTC)"
install -m 750 "$SRC/deploy/backup.sh" /usr/local/bin/hv-backup
echo "30 18 * * * root /usr/local/bin/hv-backup" > /etc/cron.d/hv-backup

echo
echo "Done. Health check:"
curl -fsS "https://$DOMAIN/api/hv/health" && echo
echo "Next: cd $APP && sudo -u hv .venv/bin/python manage.py add-doctor <아이디> <이름>"
