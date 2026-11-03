#!/usr/bin/env bash
# Daily backup: database dump, kept 14 days in /var/backups/hv.
# X-ray images are protected by Vultr automatic backups (whole disk) —
# a daily X-ray archive would fill the small disk quickly.
set -euo pipefail
DEST=/var/backups/hv
STAMP="$(TZ=Asia/Seoul date +%Y%m%d-%H%M)"
mkdir -p "$DEST"
sudo -u postgres pg_dump -Fc hv > "$DEST/hv-db-$STAMP.dump"
chmod 600 "$DEST/hv-db-$STAMP.dump"
find "$DEST" -name 'hv-*' -mtime +14 -delete
