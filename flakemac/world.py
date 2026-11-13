"""Экраны и координаты.

На macOS и Quartz, и Qt работают в точках (points) с началом в левом верхнем
углу главного экрана, поэтому перевод координат — тождественный. Масштаб
Retina (`dpr`) нужен только отрисовке, чтобы снежинки были чёткими.
"""
from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRect, QRectF
from PySide6.QtGui import QGuiApplication


@dataclass(frozen=True)
class Screen:
    index: int
    name: str
    logical: QRect          # координаты Qt (точки)
    dpr: float              # Retina: 2.0, обычный экран: 1.0
    physical: QRect         # на macOS совпадает с logical

    @property
    def work(self) -> QRect:
        return self.logical


class World:
    """Набор экранов + преобразование координат."""

    def __init__(self) -> None:
        self.screens: list[Screen] = []
        self.refresh()

    # ------------------------------------------------------------------ #
    def refresh(self) -> None:
        screens: list[Screen] = []
        for index, qscreen in enumerate(QGuiApplication.screens()):
            g = QRect(qscreen.geometry())
            dpr = float(qscreen.devicePixelRatio()) or 1.0
            screens.append(Screen(index, qscreen.name(), g, dpr, QRect(g)))
        self.screens = screens

    # ------------------------------------------------------------------ #
    def bounds(self) -> QRect:
        if not self.screens:
            return QRect(0, 0, 1920, 1080)
        r = QRect(self.screens[0].logical)
        for s in self.screens[1:]:
            r = r.united(s.logical)
        return r

    def screen_at(self, x: float, y: float) -> Screen | None:
        for s in self.screens:
            if s.logical.left() <= x <= s.logical.right() and \
                    s.logical.top() <= y <= s.logical.bottom():
                return s
        return None

    def to_logical(self, px: float, py: float) -> tuple[float, float]:
        return (px, py)

    def rect_to_logical(self, l: float, t: float, r: float, b: float) -> QRectF | None:
        if r - l <= 0 or b - t <= 0:
            return None
        return QRectF(l, t, r - l, b - t)
