#!/data/data/com.termux/files/usr/bin/bash
set -e
ZIP="${1:-/storage/emulated/0/Download/kirana-software-v0.3.2-separate-item-size.zip}"
APP="$HOME/kirana-software"
TMP="$HOME/.kirana-update-v032"

if [ ! -f "$ZIP" ]; then
  echo "❌ ZIP not found: $ZIP"
  exit 1
fi

mkdir -p "$APP"
if [ -f "$APP/kirana.db" ]; then
  BACKUP="$HOME/kirana-db-backup-$(date +%Y%m%d-%H%M%S).db"
  cp "$APP/kirana.db" "$BACKUP"
  echo "✅ Database backup: $BACKUP"
fi

rm -rf "$TMP"
mkdir -p "$TMP"
unzip -o "$ZIP" -d "$TMP" >/dev/null
cp -r "$TMP/kirana-software/." "$APP/"
rm -rf "$TMP"

source "$HOME/.kirana-venv/bin/activate"
cd "$APP"
python -m pip install --no-cache-dir -r requirements-termux.txt

echo "✅ Kirana Software v0.3.2 installed"
echo "✅ Item name and Size / Pack separated"
echo "✅ Existing imported names cleaned automatically on startup"
echo "✅ Printed invoice has a separate Size column"
echo "Open after server starts: http://127.0.0.1:8000"
python run.py
