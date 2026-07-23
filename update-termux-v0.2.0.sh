#!/data/data/com.termux/files/usr/bin/bash
set -e
ZIP="${1:-/storage/emulated/0/Download/kirana-software-v0.2.0-professional.zip}"
APP="$HOME/kirana-software"
TMP="$HOME/.kirana-update"

if [ ! -f "$ZIP" ]; then
  echo "ZIP not found: $ZIP"
  exit 1
fi

mkdir -p "$APP"
if [ -f "$APP/kirana.db" ]; then
  cp "$APP/kirana.db" "$HOME/kirana-db-backup-$(date +%Y%m%d-%H%M%S).db"
  echo "Database backup created in home folder."
fi
rm -rf "$TMP"
mkdir -p "$TMP"
unzip -o "$ZIP" -d "$TMP" >/dev/null
cp -r "$TMP/kirana-software/." "$APP/"
rm -rf "$TMP"

source "$HOME/.kirana-venv/bin/activate"
cd "$APP"
python -m pip install --no-cache-dir -r requirements-termux.txt
python run.py
