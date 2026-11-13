#!/usr/bin/env bash
# Сборка Flake.app и Flake-macOS.zip. Запускать на Mac: ./build.sh
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

echo "[1/5] Проверка Python..."
"$PY" -c "import sys; assert sys.version_info >= (3,10), 'Need Python 3.10+'; print('Python', sys.version.split()[0])"

echo "[2/5] Виртуальное окружение и зависимости..."
"$PY" -m venv .venv
source .venv/bin/activate
python -m pip install --quiet --disable-pip-version-check --upgrade pip
python -m pip install --quiet --disable-pip-version-check -r requirements.txt pyinstaller pillow

echo "[3/5] Иконка приложения..."
python make_icon.py

echo "[4/5] Сборка Flake.app..."
python -m PyInstaller --noconfirm --clean flake.spec

echo "[5/5] Подпись (ad-hoc) и архив..."
codesign --force --deep --sign - dist/Flake.app
( cd dist && rm -f Flake-macOS.zip && ditto -c -k --keepParent Flake.app Flake-macOS.zip )

echo
echo "Готово: dist/Flake.app (и dist/Flake-macOS.zip)"
echo "Установка: перетащите Flake.app в /Applications"
