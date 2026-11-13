"""Проверка собранного Flake.app на настоящем Mac (GitHub Actions).

Запускает приложение с --diagnose, ждёт отчёт и проверяет, что pyobjc
подхватился, окно снега видно и снег идёт. Код возврата != 0 — сборка падает.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

BINARY = sys.argv[1] if len(sys.argv) > 1 else "dist/Flake.app/Contents/MacOS/Flake"


def main() -> int:
    proc = subprocess.run([BINARY, "--diagnose", "--allow-multi"],
                          capture_output=True, text=True, timeout=90)
    out = proc.stdout + proc.stderr
    print(out[-6000:])
    marker = "FLAKE-DIAGNOSE "
    if marker not in out:
        print(f"::error::нет отчёта диагностики (код {proc.returncode})")
        log = Path.home() / "Library/Logs/Flake"
        for f in sorted(log.glob("*.log")):
            print(f"--- {f} ---\n{f.read_text(errors='replace')[-4000:]}")
        return 1
    text = out.split(marker, 1)[1]
    report = json.JSONDecoder().raw_decode(text)[0]

    problems = []
    if not report.get("pyobjc"):
        problems.append("pyobjc не загрузился в сборке")
    overlays = report.get("overlays") or []
    if not overlays:
        problems.append("окна снега не созданы")
    for i, o in enumerate(overlays):
        if not o.get("visible"):
            problems.append(f"окно снега {i} невидимо: {o}")
        if o.get("hidesOnDeactivate"):
            problems.append(f"окно снега {i} прячется при деактивации")
        if o.get("level", 0) < 20:
            problems.append(f"окно снега {i} ниже Dock: level={o.get('level')}")
    if report.get("flakes", 0) < 50:
        problems.append(f"снежинок слишком мало: {report.get('flakes')}")

    for p in problems:
        print(f"::error::{p}")
    print("SMOKE", "FAIL" if problems else "OK")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
