#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail

ZIP="${1:-/storage/emulated/0/Download/kirana-software-v0.4.0-purchase-returns.zip}"
APP="$HOME/kirana-software"
VENV="$HOME/.kirana-venv"
TMP="$HOME/.kirana-update-v040"

if [ ! -f "$ZIP" ]; then
  echo "❌ ZIP not found: $ZIP"
  exit 1
fi

mkdir -p "$APP"
if [ -f "$APP/kirana.db" ]; then
  BACKUP="$HOME/kirana-db-backup-$(date +%Y%m%d-%H%M%S).db"
  cp "$APP/kirana.db" "$BACKUP"
  [ -f "$APP/kirana.db-wal" ] && cp "$APP/kirana.db-wal" "$BACKUP-wal" || true
  [ -f "$APP/kirana.db-shm" ] && cp "$APP/kirana.db-shm" "$BACKUP-shm" || true
  echo "✅ Database backup: $BACKUP"
fi

rm -rf "$TMP"
mkdir -p "$TMP"
unzip -o "$ZIP" -d "$TMP" >/dev/null

if [ ! -d "$TMP/kirana-software" ]; then
  echo "❌ Invalid update ZIP: kirana-software folder missing"
  exit 1
fi

# Preserve database and local runtime files while replacing application code.
find "$APP" -mindepth 1 -maxdepth 1 \
  ! -name 'kirana.db' ! -name 'kirana.db-wal' ! -name 'kirana.db-shm' \
  -exec rm -rf {} +
cp -r "$TMP/kirana-software/." "$APP/"
rm -rf "$TMP"

if [ ! -d "$VENV" ]; then
  python -m venv "$VENV"
fi
source "$VENV/bin/activate"
cd "$APP"
python -m pip install --no-cache-dir -r requirements-termux.txt
python -m py_compile backend/app.py

if command -v node >/dev/null 2>&1; then
  node --check static/app.js
fi

echo "✅ Kirana Software v0.4.0 installed"
echo "✅ Purchase UI, item-wise returns, variant-safe import, exports and backup ready"
echo "✅ Open after server starts: http://127.0.0.1:8000"
python run.py
