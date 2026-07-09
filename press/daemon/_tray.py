"""Tray icon image generation (Pillow)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PIL.Image import Image

_ICON_SIZE = 64  # tray icon size in pixels


def _create_tray_image(holding: bool = False) -> Image:
    """Return a 64x64 RGBA PIL image used as the system-tray icon.

    Args:
        holding: When ``True``, the background is red to indicate hold state.
    """
    from PIL import Image, ImageDraw, ImageFont

    bg_color = (180, 30, 30, 255) if holding else (30, 30, 30, 255)
    img = Image.new("RGBA", (_ICON_SIZE, _ICON_SIZE), bg_color)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=40)
    bbox = draw.textbbox((0, 0), "P", font=font)
    x = (_ICON_SIZE - (bbox[2] - bbox[0])) // 2 - bbox[0]
    y = (_ICON_SIZE - (bbox[3] - bbox[1])) // 2 - bbox[1]
    draw.text((x, y), "P", fill=(255, 255, 255, 255), font=font)
    return img
