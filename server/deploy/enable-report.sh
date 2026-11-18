#!/usr/bin/env bash
# 환자 리포트 사이트를 이 서버(nginx)에서 내보내도록 설정한다. 여러 번 실행해도 안전하다.
#
# 사용 (서버에서, root):
#   bash /root/hv-src/deploy/enable-report.sh /root/hv-src/report-site
#
#   인자: 빌드한 리포트 사이트 폴더 (PC에서 `npm run build` 한 out/ 을 올려 둔 곳)
#
# 하는 일:
#   1) 리포트 파일을 /opt/hv-server/report-site 로 교체
#   2) /etc/nginx/snippets/hv-report.conf 설치
#   3) 기존 사이트 설정(/etc/nginx/sites-available/hv)의 server 블록마다
#      'include snippets/hv-report.conf;' 한 줄을 넣는다 (certbot 이 만든 https 블록 포함, 이미 있으면 건너뜀)
#   4) .env 의 REPORT_BASE_URL 을 https://<도메인>/report 로 바꾸고 hv-server 재시작
set -euo pipefail

SRC_SITE="${1:-/root/hv-src/report-site}"
HERE="$(cd "$(dirname "$0")" && pwd)"
APP=/opt/hv-server
SITE_DIR="$APP/report-site"
NGINX_SITE=/etc/nginx/sites-available/hv
SNIPPET=/etc/nginx/snippets/hv-report.conf

[ -f "$SRC_SITE/report/index.html" ] || { echo "리포트 빌드 파일이 없습니다: $SRC_SITE/report/index.html"; exit 1; }
[ -f "$NGINX_SITE" ] || { echo "nginx 사이트 설정이 없습니다: $NGINX_SITE (setup.sh 먼저)"; exit 1; }

echo "== report files → $SITE_DIR"
rm -rf "$SITE_DIR.new"
cp -r "$SRC_SITE" "$SITE_DIR.new"
chmod -R a+rX "$SITE_DIR.new"
rm -rf "$SITE_DIR.old"
[ -d "$SITE_DIR" ] && mv "$SITE_DIR" "$SITE_DIR.old"
mv "$SITE_DIR.new" "$SITE_DIR"

echo "== nginx snippet"
mkdir -p /etc/nginx/snippets
cp "$HERE/nginx-hv-report.conf" "$SNIPPET"

BACKUP=""
if ! grep -q "snippets/hv-report.conf" "$NGINX_SITE"; then
  BACKUP="$NGINX_SITE.bak.$(date +%Y%m%d%H%M%S)"
  cp "$NGINX_SITE" "$BACKUP"
  # 각 server 블록의 'location /api/hv/' 바로 앞에 include 를 넣는다
  sed -i 's|^\(\s*\)location /api/hv/ {|\1include snippets/hv-report.conf;\n\n\1location /api/hv/ {|' "$NGINX_SITE"
fi
if ! nginx -t; then
  echo "nginx 설정 검사 실패 — 원래 설정으로 되돌립니다"
  [ -n "$BACKUP" ] && cp "$BACKUP" "$NGINX_SITE"
  exit 1
fi
systemctl reload nginx

echo "== REPORT_BASE_URL"
DOMAIN="$(sed -n 's/^[[:space:]]*server_name[[:space:]]\{1,\}\([^ ;]\{1,\}\).*/\1/p' "$NGINX_SITE" | head -n1)"
[ -n "$DOMAIN" ] || { echo "nginx 설정에서 도메인을 찾지 못했습니다"; exit 1; }
URL="https://$DOMAIN/report"
if grep -qx "REPORT_BASE_URL=$URL" "$APP/.env"; then
  echo "   이미 설정됨 — 서버 재시작 안 함"
else
  if grep -q '^REPORT_BASE_URL=' "$APP/.env"; then
    sed -i "s|^REPORT_BASE_URL=.*|REPORT_BASE_URL=$URL|" "$APP/.env"
  else
    echo "REPORT_BASE_URL=$URL" >> "$APP/.env"
  fi
  systemctl restart hv-server
fi

echo
echo "완료: 환자 리포트 주소 = $URL/{hash}"
echo "확인: curl -s -o /dev/null -w '%{http_code}\\n' $URL/test   (200 이면 정상)"
