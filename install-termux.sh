#!/data/data/com.termux/files/usr/bin/bash
set -e

PROJECT_SOURCE="${1:-/storage/emulated/0/Download/kirana-software}"
PROJECT_HOME="$HOME/kirana-software"
VENV="$HOME/.kirana-venv"

pkg install python python-pip -y

if [ "$PROJECT_SOURCE" != "$PROJECT_HOME" ]; then
  rm -rf "$PROJECT_HOME"
  cp -r "$PROJECT_SOURCE" "$PROJECT_HOME"
fi

rm -rf "$VENV"
python -m venv "$VENV"
. "$VENV/bin/activate"
cd "$PROJECT_HOME"

python -m pip install --no-cache-dir --only-binary=:all: pydantic==1.10.24
python -m pip install --no-cache-dir -r requirements-termux.txt

printf '\nInstallation complete. Start later with:\n'
printf 'source ~/.kirana-venv/bin/activate && cd ~/kirana-software && python run.py\n\n'
python run.py
