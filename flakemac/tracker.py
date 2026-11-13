"""Отслеживание окон macOS: где могут расти сугробы и что непроницаемо.

Координатная система — логическая, ось Y вниз (как в Qt).
Сугроб лежит НА верхней кромке окна и растёт вверх (в сторону меньшего Y).
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass, field

from PySide6.QtCore import QRect, QRectF

from . import macapi
from .world import World

@dataclass
class Ledge:
    """Кромка, на которой может лежать снег."""
    id: str
    x: float
    top: float
    width: float
    z: int
    is_taskbar: bool = False
    can_accumulate: bool = True

    @property
    def right(self) -> float:
        return self.x + self.width


@dataclass
class Occluder:
    """Твёрдое тело окна — снежок отскакивает, снежинка отталкивается."""
    id: str
    x: float
    top: float
    right: float
    bottom: float
    z: int
    is_taskbar: bool = False

    @property
    def width(self) -> float:
        return self.right - self.x

    @property
    def height(self) -> float:
        return self.bottom - self.top


@dataclass
class Snapshot:
    ledges: list[Ledge] = field(default_factory=list)
    occluders: list[Occluder] = field(default_factory=list)
    blocked: list[QRectF] = field(default_factory=list)
    foreground: int = 0
    signature: tuple = ()


class WindowTracker:
    def __init__(self, world: World) -> None:
        self.world = world
        self._snapshot = Snapshot()
        self._last_poll = 0.0
        self._last_fg = 0
        self._own_pid = os.getpid()
        # True — снег прячется над развёрнутым окном (как в macOS-оригинале).
        self.hide_maximized = False

    # ------------------------------------------------------------------ #
    def snapshot(self, force: bool = False, active: bool = False) -> Snapshot:
        now = time.perf_counter()
        fg = macapi.frontmost_pid()
        interval = 1.0 / 30.0 if active else 1.0 / 10.0
        if not force and fg == self._last_fg and (now - self._last_poll) < interval:
            return self._snapshot
        self._last_fg = fg
        self._last_poll = now
        self._snapshot = self._poll(fg)
        return self._snapshot

    # ------------------------------------------------------------------ #
    def _poll(self, fg: int) -> Snapshot:
        world = self.world
        ledges: list[Ledge] = []
        occluders: list[Occluder] = []
        blocked: list[QRectF] = []

        monitors = macapi.enum_screens()
        windows = macapi.list_windows()
        raw: list[tuple] = []

        # Список идёт спереди назад: индекс среди обычных окон и есть z.
        z = 0
        for win in windows:
            if win.pid == self._own_pid:
                continue
            if win.layer != macapi.LAYER_NORMAL:
                continue  # Dock, строка меню, плавающие панели, оверлеи
            if win.alpha <= 0.05:
                continue
            if win.owner.lower() in macapi.SYSTEM_OWNERS:
                continue
            logical = world.rect_to_logical(win.x, win.y, win.x + win.w, win.y + win.h)
            if logical is None:
                continue
            if logical.width() < 60 or logical.height() < 40:
                continue
            raw.append((win.wid, z, logical, False, monitors))
            z += 1

        # Развёрнутые/полноэкранные окна — отдельно: они либо прячут снег,
        # либо просто игнорируются, но в любом случае не «вложены» в других.
        maximized_ids: set[int] = set()
        for hwnd, z, rect, topmost, mons in raw:
            if self._covers_monitor(rect, mons, world):
                maximized_ids.add(hwnd)
                if self.hide_maximized:
                    blocked.append(QRectF(rect))

        for hwnd, z, rect, topmost, mons in raw:
            if hwnd in maximized_ids:
                # Иначе снег идёт поверх развёрнутого окна,
                # а копится на Dock.
                continue

            # «Вложено» = окно целиком лежит на другом окне, которое ВПЕРЕДИ
            # (меньший z). Окно на фоне другого — не дочернее.
            is_nested = any(
                oh != hwnd
                and oh not in maximized_ids
                and oz < z
                and other.width() * other.height() > rect.width() * rect.height() * 1.05
                and rect.left() >= other.left() - 2
                and rect.right() <= other.right() + 2
                and rect.top() >= other.top() - 2
                and rect.bottom() <= other.bottom() + 2
                for oh, oz, other, ot, om in raw
            )

            oid = f"w{hwnd}"
            occluders.append(Occluder(oid, rect.left(), rect.top(),
                                      rect.right(), rect.bottom(), z))

            can = (
                not topmost
                and not is_nested
                and rect.height() >= 100
                and rect.width() >= 220
                and not self._near_fullscreen(rect, mons, world)
            )
            ledges.append(Ledge(oid, rect.left(), rect.top(), rect.width(), z,
                                is_taskbar=False, can_accumulate=can))

        # Dock — на его верхней кромке копится снег, по нему ездит паровозик.
        bar = macapi.dock_rect(windows)
        if bar:
            logical = world.rect_to_logical(*bar)
            if logical and logical.height() < logical.width() * 0.6:
                lid = "taskbar"
                ledges.append(Ledge(lid, logical.left(), logical.top(),
                                    logical.width(), -1000, is_taskbar=True))
                occluders.append(Occluder(lid, logical.left(), logical.top(),
                                          logical.right(), logical.bottom(),
                                          -1000, is_taskbar=True))

        signature = tuple(sorted(
            (lg.id, round(lg.x, 1), round(lg.top, 1), round(lg.width, 1))
            for lg in ledges
        ))
        return Snapshot(ledges, occluders, blocked, fg, signature)

    # ------------------------------------------------------------------ #
    def _covers_monitor(self, rect: QRectF, monitors, world: World) -> bool:
        """Окно во весь экран или во всю видимую область -> «развёрнуто»."""
        c = rect.center()
        mon = None
        for m in monitors:
            if m.x <= c.x() <= m.right and m.y <= c.y() <= m.bottom:
                mon = (QRectF(m.x, m.y, m.w, m.h), QRectF(m.vx, m.vy, m.vw, m.vh))
                break
        if mon is None:
            screen = world.screen_at(c.x(), c.y())
            if screen is None:
                return False
            mon = (QRectF(screen.logical), QRectF(screen.logical))

        for area in mon:
            if area.width() < 10 or area.height() < 10:
                continue
            if (rect.left() <= area.left() + 10
                    and rect.right() >= area.right() - 10
                    and rect.top() <= area.top() + 10
                    and rect.bottom() >= area.bottom() - 10):
                return True
        return False

    def _near_fullscreen(self, rect: QRectF, monitors, world: World) -> bool:
        c = rect.center()
        for m in monitors:
            if not (m.x <= c.x() <= m.right and m.y <= c.y() <= m.bottom):
                continue
            if rect.width() >= m.vw * 0.94 and rect.height() >= m.vh * 0.90:
                return True
        return False
