"""Музыка паровозика: NSSound (AppKit), без внешних зависимостей.

Мелодия плавно появляется, когда поезд выезжает на уборку, и стихает,
когда он уезжает. Без pyobjc (например, при тестах на Linux) молчит.
"""
from __future__ import annotations

from pathlib import Path

try:  # pragma: no cover - на Linux AppKit нет
    from AppKit import NSSound
except Exception:  # noqa: BLE001
    NSSound = None

ASSETS_AUDIO = Path(__file__).resolve().parent / "assets" / "audio"


def music_file() -> Path | None:
    bundled = ASSETS_AUDIO / "train.mp3"
    return bundled if bundled.is_file() else None


class TrainMusic:
    """Проигрывание с плавным входом и затуханием."""

    FADE_IN = 1.1
    FADE_OUT = 1.5

    def __init__(self, volume: int = 60, enabled: bool = True) -> None:
        self.path = music_file()
        self.enabled = bool(enabled) and self.path is not None and NSSound is not None
        self.volume = max(0, min(100, int(volume)))
        self._sound = None
        self._want = False
        self._preview = 0.0
        self._level = 0.0

    # ------------------------------------------------------------------ #
    def _open(self) -> bool:
        if self._sound is not None:
            return True
        if not self.enabled or self.path is None or NSSound is None:
            return False
        try:
            sound = NSSound.alloc().initWithContentsOfFile_byReference_(
                str(self.path), True)
        except Exception:  # noqa: BLE001
            sound = None
        if sound is None:
            self.enabled = False
            return False
        sound.setLoops_(True)  # трек короче, чем иной рейс
        self._sound = sound
        self._apply(0.0)
        return True

    def _apply(self, level: float) -> None:
        if self._sound is None:
            return
        value = max(0.0, min(1.0, level)) * self.volume / 100.0
        try:
            self._sound.setVolume_(float(value))
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ #
    def start(self) -> None:
        """Поезд выехал — мелодия появляется."""
        if not self.enabled or self._want:
            return
        if not self._open():
            return
        self._want = True
        try:
            if not self._sound.isPlaying():
                self._sound.setCurrentTime_(0.0)
                self._sound.play()
        except Exception:  # noqa: BLE001
            pass

    def stop(self) -> None:
        """Поезд уехал — мелодия стихает (само затухание идёт в update)."""
        self._want = False

    def preview(self, seconds: float = 3.0) -> None:
        """Короткий фрагмент — например, когда музыку только включили."""
        self._preview = max(self._preview, seconds)
        self.start()

    def previewing(self) -> bool:
        return self._preview > 0.0

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled) and self.path is not None and NSSound is not None
        if not self.enabled:
            self._want = False
            self._stop_device()

    def set_volume(self, volume: int) -> None:
        self.volume = max(0, min(100, int(volume)))
        self._apply(self._level)

    # ------------------------------------------------------------------ #
    def update(self, dt: float) -> None:
        if self._preview > 0.0:
            self._preview = max(0.0, self._preview - dt)
            if self._preview <= 0.0:
                self._want = False

        if self._sound is None:
            return

        target = 1.0 if self._want else 0.0
        if self._level < target:
            self._level = min(target, self._level + dt / self.FADE_IN)
        elif self._level > target:
            self._level = max(target, self._level - dt / self.FADE_OUT)
        self._apply(self._level)

        if not self._want and self._level <= 0.001:
            self._stop_device()

    def _stop_device(self) -> None:
        if self._sound is None:
            return
        try:
            if self._sound.isPlaying():
                self._sound.stop()
        except Exception:  # noqa: BLE001
            pass
        self._level = 0.0
        self._apply(0.0)

    def close(self) -> None:
        self._want = False
        self._stop_device()
        self._sound = None
