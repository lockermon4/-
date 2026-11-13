"""Настройки Flake для macOS: ~/Library/Application Support/FlakeMac/settings.json."""
from __future__ import annotations

import json
import math
from pathlib import Path

APP_DIR = Path.home() / "Library" / "Application Support" / "FlakeMac"
SETTINGS_PATH = APP_DIR / "settings.json"

DEFAULTS = {
    "intensity": 0.7,
    "mouse_enabled": True,
    "paused": False,
    "hide_on_maximized": False,
    "train_enabled": True,
    "music_enabled": True,
    "music_volume": 60,
    "snowman_scale": 1.55,
    "wallpaper_backup": "",
    "autostart": False,
    "fps_limit": 30,
}


# Допустимые диапазоны числовых настроек: (min, max, тип).
_RANGES = {
    "intensity": (0.25, 1.4, float),
    "music_volume": (0, 100, int),
    "snowman_scale": (0.6, 3.0, float),
    "fps_limit": (10, 60, int),
}


def _validate(key: str, value):
    """Значение из settings.json -> безопасное значение или None (= по умолчанию).

    Файл правится руками, поэтому ничему в нём не доверяем: строки вместо
    чисел, NaN, бесконечность и прочее не должны ронять приложение.
    """
    default = DEFAULTS[key]
    if key in _RANGES:
        lo, hi, kind = _RANGES[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return None
        if not math.isfinite(value):
            return None
        return kind(min(hi, max(lo, value)))
    if isinstance(default, bool):
        return value if isinstance(value, bool) else None
    if isinstance(default, str):
        return value[:4096] if isinstance(value, str) else None
    return None


class Settings:
    def __init__(self) -> None:
        self.data = dict(DEFAULTS)
        self.load()

    # ------------------------------------------------------------------ #
    def load(self) -> None:
        raw = {}
        try:
            if SETTINGS_PATH.exists():
                raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8-sig"))
        except Exception:  # noqa: BLE001 — битый файл: работаем на умолчаниях
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        for key, value in raw.items():
            if key in DEFAULTS:
                clean = _validate(key, value)
                if clean is not None:
                    self.data[key] = clean

    def save(self) -> None:
        try:
            APP_DIR.mkdir(parents=True, exist_ok=True)
            SETTINGS_PATH.write_text(
                json.dumps(self.data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    # ------------------------------------------------------------------ #
    def __getitem__(self, key: str):
        return self.data.get(key, DEFAULTS.get(key))

    def __setitem__(self, key: str, value) -> None:
        self.data[key] = value
        self.save()

    def toggle(self, key: str) -> bool:
        value = not bool(self[key])
        self[key] = value
        return value
