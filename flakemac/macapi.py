"""Тонкая обёртка над macOS (Quartz / AppKit через pyobjc).

Все координаты — в ТОЧКАХ (points) с началом в левом верхнем углу главного
экрана и осью Y вниз. Это ровно та же система, что у Qt на macOS, поэтому
никакого перевода «физические пиксели -> логические» не нужно.

Если pyobjc недоступен (например, тесты на Linux), функции возвращают
безопасные заглушки, а `AVAILABLE` равен False.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass

try:  # pragma: no cover - на Linux pyobjc нет
    import objc
    import Quartz
    from AppKit import (NSApplication, NSColor, NSEvent, NSScreen,
                        NSWorkspace)
    from Foundation import NSURL

    AVAILABLE = True
except Exception:  # noqa: BLE001
    objc = Quartz = None
    NSApplication = NSColor = NSEvent = NSScreen = NSWorkspace = NSURL = None
    AVAILABLE = False


# Уровни окон (CGWindowLevel.h).
LAYER_NORMAL = 0
LAYER_DOCK = 20
OVERLAY_LEVEL = 25          # NSStatusWindowLevel: выше Dock, ниже меню

# NSWindowCollectionBehavior
_CB_ALL_SPACES = 1 << 0
_CB_STATIONARY = 1 << 4
_CB_IGNORES_CYCLE = 1 << 6
_CB_FULLSCREEN_AUX = 1 << 8

# Системные процессы, чьи окна не являются «мебелью» рабочего стола.
SYSTEM_OWNERS = {
    "window server", "dock", "systemuiserver", "control center",
    "controlcenter", "notification center", "notificationcenter",
    "spotlight", "screenshot", "wallpaper", "loginwindow",
    "textinputmenuagent", "universal control", "screencaptureui",
}


# --------------------------------------------------------------------------- #
#  Окна
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class WinInfo:
    wid: int
    pid: int
    owner: str
    layer: int
    alpha: float
    x: float
    y: float
    w: float
    h: float


def _copy_windows(options) -> list[WinInfo]:
    if not AVAILABLE:
        return []
    info = Quartz.CGWindowListCopyWindowInfo(options, Quartz.kCGNullWindowID) or []
    out: list[WinInfo] = []
    for item in info:
        try:
            b = item.get("kCGWindowBounds") or {}
            out.append(WinInfo(
                wid=int(item.get("kCGWindowNumber", 0)),
                pid=int(item.get("kCGWindowOwnerPID", 0)),
                owner=str(item.get("kCGWindowOwnerName", "") or ""),
                layer=int(item.get("kCGWindowLayer", 0)),
                alpha=float(item.get("kCGWindowAlpha", 1.0)),
                x=float(b.get("X", 0)), y=float(b.get("Y", 0)),
                w=float(b.get("Width", 0)), h=float(b.get("Height", 0)),
            ))
        except Exception:  # noqa: BLE001
            continue
    return out


def list_windows() -> list[WinInfo]:
    """Все видимые окна текущего пространства (Space), спереди назад,
    включая системные слои (Dock, строка меню) — фильтрует tracker."""
    if not AVAILABLE:
        return []
    return _copy_windows(Quartz.kCGWindowListOptionOnScreenOnly)


def frontmost_pid() -> int:
    if not AVAILABLE:
        return 0
    try:
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return int(app.processIdentifier()) if app is not None else 0
    except Exception:  # noqa: BLE001
        return 0


# --------------------------------------------------------------------------- #
#  Экраны
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class ScreenRect:
    """Экран: полный кадр и видимая область (без меню и Dock), координаты Qt."""
    x: float
    y: float
    w: float
    h: float
    vx: float
    vy: float
    vw: float
    vh: float
    primary: bool

    @property
    def right(self) -> float:
        return self.x + self.w

    @property
    def bottom(self) -> float:
        return self.y + self.h

    @property
    def visible_bottom(self) -> float:
        return self.vy + self.vh


def _primary_height() -> float:
    screens = NSScreen.screens()
    if not screens:
        return 0.0
    return float(screens[0].frame().size.height)


def _to_top_left(rect, primary_h: float) -> tuple[float, float, float, float]:
    """NSRect (начало снизу слева) -> (x, y, w, h) с началом сверху слева."""
    x = float(rect.origin.x)
    w = float(rect.size.width)
    h = float(rect.size.height)
    y = primary_h - (float(rect.origin.y) + h)
    return (x, y, w, h)


def cocoa_rect(x: float, y: float, w: float, h: float):
    """(x, y, w, h) в координатах Qt -> NSRect в координатах Cocoa."""
    primary_h = _primary_height()
    return ((x, primary_h - (y + h)), (w, h))


def enum_screens() -> list[ScreenRect]:
    if not AVAILABLE:
        return []
    out: list[ScreenRect] = []
    try:
        primary_h = _primary_height()
        for i, s in enumerate(NSScreen.screens() or []):
            fx, fy, fw, fh = _to_top_left(s.frame(), primary_h)
            vx, vy, vw, vh = _to_top_left(s.visibleFrame(), primary_h)
            out.append(ScreenRect(fx, fy, fw, fh, vx, vy, vw, vh, i == 0))
    except Exception:  # noqa: BLE001
        return []
    return out


# --------------------------------------------------------------------------- #
#  Dock (аналог панели задач Windows)
# --------------------------------------------------------------------------- #

def dock_rect(windows: list[WinInfo] | None = None,
              screens: list[ScreenRect] | None = None):
    """Полоса Dock внизу экрана, если он видим и не прячется автоматически.

    Возвращает (x, top, right, bottom) в координатах Qt или None.
    Dock сбоку экрана не учитывается — на нём снегу лежать негде.
    `windows` и `screens` можно передать уже полученными, чтобы не
    опрашивать систему повторно.
    """
    if not AVAILABLE:
        return None
    for scr in screens if screens is not None else enum_screens():
        gap = scr.bottom - scr.visible_bottom
        if gap < 12:  # автоскрытие или Dock на другом экране/сбоку
            continue
        top = scr.visible_bottom
        left, right = scr.x, scr.right
        # Пытаемся найти саму «подложку» Dock, чтобы снег не висел в воздухе.
        try:
            for win in windows if windows is not None else list_windows():
                if win.owner.lower() != "dock" or win.layer != LAYER_DOCK:
                    continue
                if win.h > gap * 2.5 or win.w >= scr.w * 0.98 or win.w < 80:
                    continue
                if win.y + win.h < top - 4 or win.y > scr.bottom:
                    continue
                left, right = win.x, win.x + win.w
                top = max(top, win.y)
                break
        except Exception:  # noqa: BLE001
            pass
        return (left, top, right, scr.bottom)
    return None


# --------------------------------------------------------------------------- #
#  Ввод
# --------------------------------------------------------------------------- #

def cursor_pos() -> tuple[float, float]:
    if AVAILABLE:
        try:
            event = Quartz.CGEventCreate(None)
            loc = Quartz.CGEventGetLocation(event)
            return (float(loc.x), float(loc.y))
        except Exception:  # noqa: BLE001
            pass
    from PySide6.QtGui import QCursor

    p = QCursor.pos()
    return (float(p.x()), float(p.y()))


def mouse_buttons() -> tuple[bool, bool]:
    """(левая, правая) кнопка зажата — глобально, без прав «Универсального доступа»."""
    if not AVAILABLE:
        return (False, False)
    try:
        mask = int(NSEvent.pressedMouseButtons())
        return (bool(mask & 1), bool(mask & 2))
    except Exception:  # noqa: BLE001
        return (False, False)


# --------------------------------------------------------------------------- #
#  Окно-оверлей
# --------------------------------------------------------------------------- #

def _ns_window(win_id: int):
    view = objc.objc_object(c_void_p=ctypes.c_void_p(int(win_id)))
    return view.window()


def configure_overlay(win_id: int, x: float, y: float, w: float, h: float) -> None:
    """Прозрачное окно поверх всего, на всех столах, без кликов и тени."""
    if not AVAILABLE:
        return
    try:
        window = _ns_window(win_id)
        if window is None:
            return
        # Окно не должно прятаться, когда приложение неактивно: Flake живёт
        # в строке меню и активным почти не бывает (NSPanel по умолчанию
        # скрывается при деактивации — из-за этого снега не было видно).
        if window.respondsToSelector_("setHidesOnDeactivate:"):
            window.setHidesOnDeactivate_(False)
        window.setCanHide_(False)
        window.setLevel_(OVERLAY_LEVEL)
        window.setCollectionBehavior_(_CB_ALL_SPACES | _CB_STATIONARY
                                      | _CB_IGNORES_CYCLE | _CB_FULLSCREEN_AUX)
        window.setIgnoresMouseEvents_(True)
        window.setHasShadow_(False)
        window.setOpaque_(False)
        window.setBackgroundColor_(NSColor.clearColor())
        # Qt не даёт окну заходить под строку меню — ставим кадр напрямую.
        window.setFrame_display_(cocoa_rect(x, y, w, h), False)
        window.orderFrontRegardless()
    except Exception:  # noqa: BLE001
        import logging

        logging.getLogger("flake").exception("configure_overlay failed")


def describe_overlay(win_id: int) -> dict:
    """Состояние нативного окна — для режима диагностики."""
    if not AVAILABLE:
        return {"pyobjc": False}
    try:
        w = _ns_window(win_id)
        if w is None:
            return {"nswindow": None}
        f = w.frame()
        return {
            "class": str(w.className()),
            "visible": bool(w.isVisible()),
            "onActiveSpace": bool(w.isOnActiveSpace()),
            "occlusionVisible": bool(int(w.occlusionState()) & (1 << 1)),
            "level": int(w.level()),
            "alpha": float(w.alphaValue()),
            "hidesOnDeactivate": bool(w.hidesOnDeactivate()),
            "ignoresMouse": bool(w.ignoresMouseEvents()),
            "frame": [f.origin.x, f.origin.y, f.size.width, f.size.height],
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": repr(exc)}


def hide_from_dock() -> None:
    """Приложение живёт только в строке меню: без значка в Dock и Cmd+Tab."""
    if not AVAILABLE:
        return
    try:
        NSApplication.sharedApplication().setActivationPolicy_(1)  # Accessory
    except Exception:  # noqa: BLE001
        pass


def activate_app() -> None:
    """Вывести диалоги приложения на передний план."""
    if not AVAILABLE:
        return
    try:
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
    except Exception:  # noqa: BLE001
        pass


# --------------------------------------------------------------------------- #
#  Обои рабочего стола
# --------------------------------------------------------------------------- #

def set_wallpaper(path: str) -> bool:
    """Поставить картинку на все экраны в режиме «заполнить»."""
    if not AVAILABLE:
        return False
    try:
        ws = NSWorkspace.sharedWorkspace()
        url = NSURL.fileURLWithPath_(str(path))
        options = {
            "NSWorkspaceDesktopImageScalingKey": 3,       # пропорционально
            "NSWorkspaceDesktopImageAllowClippingKey": True,
        }
        ok = False
        for screen in NSScreen.screens() or []:
            result = ws.setDesktopImageURL_forScreen_options_error_(
                url, screen, options, None)
            success = result[0] if isinstance(result, tuple) else result
            ok = ok or bool(success)
        return ok
    except Exception:  # noqa: BLE001
        return False


def current_wallpaper() -> str:
    if not AVAILABLE:
        return ""
    try:
        screen = NSScreen.mainScreen() or (NSScreen.screens() or [None])[0]
        if screen is None:
            return ""
        url = NSWorkspace.sharedWorkspace().desktopImageURLForScreen_(screen)
        return str(url.path()) if url is not None else ""
    except Exception:  # noqa: BLE001
        return ""
