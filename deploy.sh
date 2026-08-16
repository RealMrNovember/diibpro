#!/usr/bin/env bash
# DİİBPro — tek komut dağıtım: ./deploy.sh  (Git Bash / Linux)
# Kod dosyalarını paketler, sunucuya yükler, servisi yeniden başlatır.
# Veritabanına ve uploads klasörüne DOKUNMAZ.
set -euo pipefail

SUNUCU="root@31.40.199.47"
HEDEF="/www/wwwroot/diibpro.cicibyte.com/app"
SERVIS="diibpro"

cd "$(dirname "$0")"
echo "📦 Paketleniyor..."
tar --exclude='__pycache__' -czf /tmp/diibpro-deploy.tar.gz 2>/dev/null \
    backend frontend docs requirements.txt README.md todo.md deploy.sh || \
tar --exclude='__pycache__' -czf diibpro-deploy.tar.gz \
    backend frontend docs requirements.txt README.md todo.md deploy.sh

PKG=$([ -f /tmp/diibpro-deploy.tar.gz ] && echo /tmp/diibpro-deploy.tar.gz || echo diibpro-deploy.tar.gz)

echo "⬆️  Yükleniyor..."
scp -q "$PKG" "$SUNUCU:/tmp/diibpro-deploy.tar.gz"
rm -f diibpro-deploy.tar.gz 2>/dev/null || true

echo "🚀 Kurulum + yeniden başlatma..."
ssh "$SUNUCU" "
set -e
cd $HEDEF
tar -xzf /tmp/diibpro-deploy.tar.gz && rm /tmp/diibpro-deploy.tar.gz
../venv/bin/pip install -q -r requirements.txt
../venv/bin/python -c 'from backend import db; db.init_db()'   # migrasyonlar
chown -R www:www .
systemctl restart $SERVIS
sleep 3
curl -s -o /dev/null -w 'Sağlık kontrolü: HTTP %{http_code}\n' http://127.0.0.1:8756/
"
echo "✅ Dağıtım tamam — https://diibpro.cicibyte.com"
