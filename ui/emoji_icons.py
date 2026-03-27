"""Emoji icon helpers for stable button icon rendering."""
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QFontDatabase, QIcon, QPainter, QPixmap


def _pick_emoji_font(pixel_size: int) -> QFont:
    preferred_families = [
        "Segoe UI Emoji",
        "Apple Color Emoji",
        "Noto Color Emoji",
        "Twitter Color Emoji",
    ]
    try:
        available = set(QFontDatabase.families())
    except Exception:
        available = set()

    for family in preferred_families:
        if family in available:
            font = QFont(family)
            font.setPixelSize(pixel_size)
            return font

    fallback = QFont()
    fallback.setPixelSize(pixel_size)
    return fallback


def emoji_icon(emoji: str, icon_size: int = 16) -> QIcon:
    pixmap = QPixmap(icon_size, icon_size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    painter.setFont(_pick_emoji_font(max(12, int(icon_size * 0.9))))
    painter.drawText(pixmap.rect(), int(Qt.AlignmentFlag.AlignCenter), emoji)
    painter.end()

    return QIcon(pixmap)


def set_button_emoji_icon(button, emoji: str, icon_size: int = 16) -> None:
    try:
        button.setIcon(emoji_icon(emoji, icon_size))
        button.setIconSize(QSize(icon_size, icon_size))
    except Exception:
        # Icon rendering should never block app startup or button usability.
        return
