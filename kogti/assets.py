"""Raster assets from the design book: avatars, wallpapers, menu glyph."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from . import color as C
from .tokens import Tokens
from .tree import Tree

WALL_W, WALL_H = 3840, 2160
ICON_SIZES = (16, 22, 24, 32, 48, 64, 96, 128, 256)
AVATARS = {
    "profile": "06-profil-b_circle.png",
    "profile-hex": "06-profil-b_hex.png",
    "profile-split": "06-profil_hex.png",
    "axe": "07-ledorub-inv_circle.png",
    "axe-hex": "07-ledorub-inv_hex.png",
    "axe-square": "07-ledorub-inv_square.png",
}


def _png(im: Image.Image, **kw) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True, **kw)
    return buf.getvalue()


def _open(t: Tokens, name: str) -> Image.Image:
    p = t.root / "design" / name
    if not p.exists():
        raise SystemExit(f"design asset missing: {p}")
    return Image.open(p).convert("RGBA")


def _square(im: Image.Image, size: int) -> Image.Image:
    return im.resize((size, size), Image.LANCZOS)


def avatars(t: Tokens, tree: Tree) -> dict[str, str]:
    """Every avatar variant at 512px; returns name -> installed path."""
    out = {}
    for key, fname in AVATARS.items():
        dest = f"usr/share/{t.id}/avatars/{key}.png"
        tree.add(dest, _png(_square(_open(t, fname), 512)))
        out[key] = "/" + dest
    default = t.raw["assets"]["avatar"]
    key = next((k for k, v in AVATARS.items() if v == default), "profile")
    tree.add(f"usr/share/pixmaps/{t.id}-avatar.png", _png(_square(_open(t, default), 512)))
    out["default"] = out[key]
    return out


def tile_of(im: Image.Image, grid: int = 3) -> Image.Image:
    """The pattern PNGs are a grid x grid repeat of one seamless tile; return that tile."""
    w, h = im.size
    return im.crop((0, 0, w // grid, h // grid))


def tiled(tile: Image.Image, w: int, h: int) -> Image.Image:
    canvas = Image.new("RGB", (w, h))
    tw, th = tile.size
    for y in range(0, h, th):
        for x in range(0, w, tw):
            canvas.paste(tile, (x, y))
    return canvas


def wallpapers(t: Tokens, tree: Tree) -> dict[str, str]:
    ink = C.parse(t.ink)
    out: dict[str, str] = {}
    base = f"usr/share/backgrounds/{t.id}"

    logo = _open(t, t.raw["assets"]["wallpaper_logo"]).convert("RGB")
    logo = logo.resize((WALL_H, WALL_H), Image.LANCZOS)
    canvas = Image.new("RGB", (WALL_W, WALL_H), ink)
    canvas.paste(logo, ((WALL_W - WALL_H) // 2, 0))
    tree.add(f"{base}/{t.id}-logo.png", _png(canvas))
    out["logo"] = f"/{base}/{t.id}-logo.png"

    strength = float(t.raw["assets"]["pattern_strength"])
    flat = Image.new("RGB", (WALL_W, WALL_H), ink)
    for key, fname in t.raw["assets"]["patterns"].items():
        tile = tile_of(_open(t, fname).convert("RGB"))
        wall = Image.blend(flat, tiled(tile, WALL_W, WALL_H), strength)
        tree.add(f"{base}/{t.id}-{key}.png", _png(wall))
        out[key] = f"/{base}/{t.id}-{key}.png"
    return out


def menu_icons(t: Tokens, tree: Tree) -> None:
    """Whisker menu button glyph in all common sizes, installed in the icon theme."""
    src = _open(t, t.raw["assets"]["menu_glyph"])
    box = src.getbbox()
    if box:
        src = src.crop(box)
    for size in ICON_SIZES:
        pad = max(1, round(size * 0.10))
        inner = size - 2 * pad
        g = src.copy()
        g.thumbnail((inner, inner), Image.LANCZOS)
        im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        im.paste(g, ((size - g.width) // 2, (size - g.height) // 2), g)
        data = _png(im)
        for ctx, name in (("apps", f"{t.id}-menu"), ("places", "start-here"), ("places", f"distributor-logo")):
            tree.add(f"usr/share/icons/{t.name}/{size}x{size}/{ctx}/{name}.png", data)
