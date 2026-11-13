"""Фон окна установщика (DMG): снег, надпись и стрелка к «Программам».

python packaging/make_dmg_background.py dmg-background.png
Рядом пишется dmg-background@2x.png для Retina (их склеивает tiffutil).
"""
from __future__ import annotations

import math
import random
import sys

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QBrush, QColor, QFont, QImage, QLinearGradient,
                           QPainter, QPainterPath, QPen, QRadialGradient)
from PySide6.QtWidgets import QApplication

WIDTH, HEIGHT = 660, 400          # размер окна в точках
TITLE = "Special for Kseniya! <3"
APP_X, ICON_Y, APPS_X = 165, 200, 495   # центры иконок (как в create-dmg)
DRIFT_TOP = HEIGHT - 142               # подписи иконок Finder тёмные — пусть лежат на снегу


def _heart(p: QPainter, cx: float, cy: float, size: float, color: QColor) -> None:
    path = QPainterPath()
    path.moveTo(cx, cy + size * 0.35)
    path.cubicTo(cx - size * 1.1, cy - size * 0.35, cx - size * 0.45, cy - size * 1.05,
                 cx, cy - size * 0.45)
    path.cubicTo(cx + size * 0.45, cy - size * 1.05, cx + size * 1.1, cy - size * 0.35,
                 cx, cy + size * 0.35)
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(color))
    p.drawPath(path)


def render(scale: int = 1) -> QImage:
    img = QImage(WIDTH * scale, HEIGHT * scale, QImage.Format.Format_ARGB32_Premultiplied)
    img.setDotsPerMeterX(int(72 * scale / 0.0254))
    img.setDotsPerMeterY(int(72 * scale / 0.0254))
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    p.scale(scale, scale)

    sky = QLinearGradient(0, 0, 0, HEIGHT)
    sky.setColorAt(0.0, QColor("#0b1a33"))
    sky.setColorAt(0.6, QColor("#1d3d63"))
    sky.setColorAt(1.0, QColor("#3c6a92"))
    p.fillRect(QRectF(0, 0, WIDTH, HEIGHT), QBrush(sky))

    # Сугроб внизу.
    drift = QPainterPath()
    drift.moveTo(0, HEIGHT)
    drift.lineTo(0, DRIFT_TOP)
    for x in range(0, WIDTH + 20, 20):
        drift.lineTo(x, DRIFT_TOP - 6 * math.sin(x * 0.021) - 5 * math.sin(x * 0.057))
    drift.lineTo(WIDTH, HEIGHT)
    drift.closeSubpath()
    snow = QLinearGradient(0, DRIFT_TOP - 20, 0, HEIGHT)
    snow.setColorAt(0.0, QColor("#ffffff"))
    snow.setColorAt(1.0, QColor("#cfe1f2"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(snow))
    p.drawPath(drift)

    # Снежинки.
    rnd = random.Random(1402)
    for _ in range(170):
        x, y = rnd.uniform(0, WIDTH), rnd.uniform(0, DRIFT_TOP - 12)
        r = rnd.uniform(0.6, 2.4)
        p.setBrush(QBrush(QColor(255, 255, 255, rnd.randint(60, 210))))
        p.drawEllipse(QPointF(x, y), r, r)

    # Мягкое свечение под иконками, чтобы они читались на тёмном фоне.
    for cx in (APP_X, APPS_X):
        glow = QRadialGradient(cx, ICON_Y, 70)
        glow.setColorAt(0.0, QColor(255, 255, 255, 46))
        glow.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setBrush(QBrush(glow))
        p.drawEllipse(QPointF(cx, ICON_Y), 70, 70)

    # Надпись.
    # Каллиграфия есть на любом Mac; на других системах — запасные шрифты.
    font = QFont()
    font.setFamilies(["Snell Roundhand", "Apple Chancery", "Zapfino",
                      "Brush Script MT", "Georgia", "serif"])
    font.setPixelSize(40)
    font.setBold(True)
    p.setFont(font)
    text_w = p.fontMetrics().horizontalAdvance(TITLE)
    title_rect = QRectF(0, 28, WIDTH, 70)
    p.setPen(QPen(QColor(0, 0, 0, 90)))
    p.drawText(title_rect.translated(0, 2), int(Qt.AlignmentFlag.AlignCenter), TITLE)
    p.setPen(QPen(QColor("#ffe3ee")))
    p.drawText(title_rect, int(Qt.AlignmentFlag.AlignCenter), TITLE)
    for side in (-1, 1):
        _heart(p, WIDTH / 2 + side * (text_w / 2 + 22), 66, 9,
               QColor(255, 110, 150, 210))

    hint = QFont()
    hint.setFamilies(["Helvetica Neue", "Helvetica", "Arial", "sans-serif"])
    hint.setPixelSize(14)
    p.setFont(hint)
    p.setPen(QPen(QColor(220, 232, 248, 220)))
    p.drawText(QRectF(0, 104, WIDTH, 24), int(Qt.AlignmentFlag.AlignCenter),
               "Перетащите Flake в «Программы»")

    # Стрелка.
    pen = QPen(QColor(255, 255, 255, 210))
    pen.setWidthF(4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    x0, x1, y = APP_X + 66, APPS_X - 66, ICON_Y - 6
    arc = QPainterPath()
    arc.moveTo(x0, y)
    arc.quadTo((x0 + x1) / 2, y - 26, x1, y)
    p.drawPath(arc)
    p.drawLine(QPointF(x1, y), QPointF(x1 - 14, y - 10))
    p.drawLine(QPointF(x1, y), QPointF(x1 - 16, y + 6))

    p.end()
    return img


def main() -> int:
    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841
    out = sys.argv[1] if len(sys.argv) > 1 else "dmg-background.png"
    out2x = out[:-4] + "@2x.png" if out.endswith(".png") else out + "@2x.png"
    ok = render(1).save(out, "PNG") and render(2).save(out2x, "PNG")
    print("dmg background:", out, out2x, ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
