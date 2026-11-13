#!/usr/bin/env bash
# Сборка Flake.app и Flake-macOS.zip. Запускать на Mac: ./build.sh
set -euo pipefail
cd "$(dirname "$0")"

PY="${PYTHON:-python3}"

echo "[1/6] Проверка Python..."
"$PY" -c "import sys; assert sys.version_info >= (3,10), 'Need Python 3.10+'; print('Python', sys.version.split()[0])"

echo "[2/6] Виртуальное окружение и зависимости..."
"$PY" -m venv .venv
source .venv/bin/activate
python -m pip install --quiet --disable-pip-version-check --upgrade pip
python -m pip install --quiet --disable-pip-version-check -r requirements.txt pyinstaller==6.22.3 pillow==13.0.0

echo "[3/6] Иконка приложения..."
python make_icon.py

echo "[4/6] Сборка Flake.app..."
python -m PyInstaller --noconfirm --clean flake.spec

echo "[5/6] Подпись (ad-hoc) и архив..."
codesign --force --deep --sign - dist/Flake.app
( cd dist && rm -f Flake-macOS.zip && ditto -c -k --keepParent Flake.app Flake-macOS.zip )

echo "[6/6] Установщик DMG..."
if command -v create-dmg >/dev/null 2>&1; then
  rm -rf dist/dmg-src dist/Flake.dmg
  mkdir -p dist/dmg-src
  cp -R dist/Flake.app dist/dmg-src/
  python packaging/make_dmg_background.py dist/dmg-background.png
  tiffutil -cathidpicheck dist/dmg-background.png dist/dmg-background@2x.png \
    -out dist/dmg-background.tiff
  # Finder-оформление через AppleScript на CI иногда отваливается — пробуем ещё раз.
  for attempt in 1 2 3; do
    if create-dmg \
        --volname "Flake" \
        --background dist/dmg-background.tiff \
        --window-pos 200 120 \
        --window-size 660 428 \
        --icon-size 96 \
        --text-size 13 \
        --icon "Flake.app" 165 200 \
        --hide-extension "Flake.app" \
        --app-drop-link 495 200 \
        dist/Flake.dmg dist/dmg-src; then
      break
    fi
    echo "create-dmg: попытка $attempt не удалась"
    rm -f dist/Flake.dmg dist/rw.*.dmg
    [ "$attempt" = 3 ] && exit 1
    sleep 5
  done
  codesign --force --sign - dist/Flake.dmg
else
  echo "create-dmg не найден (brew install create-dmg) — DMG пропущен"
fi

echo
echo "Готово: dist/Flake.app, dist/Flake-macOS.zip и dist/Flake.dmg"
echo "Установка: перетащите Flake.app в /Applications"
