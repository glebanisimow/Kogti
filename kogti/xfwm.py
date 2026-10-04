"""xfwm4 window decoration: flat PNGs drawn with PIL, square buttons, amber line under the focused title bar."""
from __future__ import annotations

import io
import math

from PIL import Image, ImageDraw

from . import color as C
from .tokens import Tokens
from .tree import Tree

SS = 4  # supersampling for glyphs
STATES = ("active", "inactive", "prelight", "pressed")
GLYPHS = ("close", "hide", "maximize", "maximize-toggled", "menu", "shade", "shade-toggled", "stick", "stick-toggled")


def _png(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _glyph(kind: str, size: int, color: str, stroke: float) -> Image.Image:
    n = size * SS
    big = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    col = C.parse(color) + (255,)
    w = max(1, round(stroke * SS))
    c = size / 2

    def P(x: float, y: float) -> tuple[float, float]:
        return (x * SS, y * SS)

    r = size * 0.17  # half extent of the basic glyph
    if kind == "close":
        d.line([P(c - r, c - r), P(c + r, c + r)], fill=col, width=w)
        d.line([P(c + r, c - r), P(c - r, c + r)], fill=col, width=w)
    elif kind == "hide":
        d.rectangle([P(c - r, c + r - stroke), P(c + r, c + r)], fill=col)
    elif kind == "maximize":
        d.rectangle([P(c - r, c - r), P(c + r, c + r)], outline=col, width=w)
    elif kind == "maximize-toggled":
        o = r * 0.45
        d.rectangle([P(c - r + o * 2, c - r - o), P(c + r + o, c + r - o * 2)], outline=col, width=w)
        d.rectangle([P(c - r - o, c - r + o * 2), P(c + r - o * 2, c + r + o)], outline=col, width=w)
    elif kind == "shade":
        d.line([P(c - r, c + r * 0.5), P(c, c - r * 0.5), P(c + r, c + r * 0.5)], fill=col, width=w, joint="curve")
    elif kind == "shade-toggled":
        d.line([P(c - r, c - r * 0.5), P(c, c + r * 0.5), P(c + r, c - r * 0.5)], fill=col, width=w, joint="curve")
    elif kind == "stick":
        d.ellipse([P(c - r * 0.8, c - r * 0.8), P(c + r * 0.8, c + r * 0.8)], outline=col, width=w)
    elif kind == "stick-toggled":
        d.ellipse([P(c - r * 0.8, c - r * 0.8), P(c + r * 0.8, c + r * 0.8)], fill=col)
    elif kind == "menu":
        pts = [P(c + r * 1.1 * math.cos(math.radians(a)), c + r * 1.1 * math.sin(math.radians(a))) for a in range(30, 390, 60)]
        d.line(pts + [pts[0]], fill=col, width=w, joint="curve")
    else:
        raise ValueError(kind)
    return big.resize((size, size), Image.LANCZOS)


def build(t: Tokens) -> Tree:
    s = t.surfaces
    H = int(t.raw["geometry"]["titlebar"])
    B = int(t.raw["geometry"]["border"])
    L = int(t.raw["geometry"]["accent_line"])
    tree = Tree()
    base = f"usr/share/themes/{t.name}/xfwm4"

    pal = {
        "active": {"bg": s["header"], "line": t.amber, "edge": s["border"], "fg": t.bone, "line_h": L},
        "inactive": {"bg": s["win"], "line": s["border"], "edge": s["header"], "fg": s["dim"], "line_h": 1},
    }

    def frame_px(kind: str, state: str):
        p = pal[state]
        bg, line, edge, lh = p["bg"], p["line"], p["edge"], p["line_h"]
        if kind == "title":
            w, h = 4, H
            im = Image.new("RGB", (w, h), bg)
            px = im.load()
            for x in range(w):
                px[x, 0] = C.parse(edge)
                for y in range(H - lh, H):
                    px[x, y] = C.parse(line)
            return im
        if kind in ("top-left", "top-right"):
            im = Image.new("RGB", (B, H), bg)
            px = im.load()
            ox = 0 if kind == "top-left" else B - 1
            for y in range(H):
                px[ox, y] = C.parse(edge)
            for x in range(B):
                px[x, 0] = C.parse(edge)
                for y in range(H - lh, H):
                    px[x, y] = C.parse(line)
            return im
        if kind in ("left", "right"):
            im = Image.new("RGB", (B, 1), bg)
            im.putpixel((0 if kind == "left" else B - 1, 0), C.parse(edge))
            return im
        if kind == "bottom":
            im = Image.new("RGB", (1, B), bg)
            im.putpixel((0, B - 1), C.parse(edge))
            return im
        if kind in ("bottom-left", "bottom-right"):
            im = Image.new("RGB", (B, B), bg)
            px = im.load()
            ox = 0 if kind == "bottom-left" else B - 1
            for i in range(B):
                px[ox, i] = C.parse(edge)
                px[i, B - 1] = C.parse(edge)
            return im
        raise ValueError(kind)

    for state in ("active", "inactive"):
        for n in range(1, 6):
            tree.add(f"{base}/title-{n}-{state}.png", _png(frame_px("title", state)))
        for k in ("top-left", "top-right", "left", "right", "bottom", "bottom-left", "bottom-right"):
            tree.add(f"{base}/{k}-{state}.png", _png(frame_px(k, state)))

    size = H
    for kind in GLYPHS:
        toggled = kind.endswith("-toggled") or kind == "stick-toggled"
        for state in STATES:
            if state == "inactive":
                bg, fg, line, lh, edge = s["win"], s["dim"], s["border"], 1, s["header"]
                if toggled:
                    fg = C.mix(s["dim"], t.amber, 0.5)
            else:
                bg, fg, line, lh, edge = s["header"], t.bone, t.amber, L, s["border"]
                if toggled:
                    fg = t.amber
                if state == "prelight":
                    bg = t.danger if kind == "close" else s["raised"]
                    fg = t.on(t.danger) if kind == "close" else t.bone
                elif state == "pressed":
                    bg = C.mix(t.danger, t.ink, 0.25) if kind == "close" else t.amber
                    fg = t.bone if kind == "close" else t.ink
            im = Image.new("RGBA", (size, size), C.parse(bg) + (255,))
            d = ImageDraw.Draw(im)
            d.line([(0, 0), (size, 0)], fill=C.parse(edge) + (255,))
            d.rectangle([0, size - lh, size, size], fill=C.parse(line) + (255,))
            im.alpha_composite(_glyph(kind, size, fg, stroke=1.8))
            tree.add(f"{base}/{kind}-{state}.png", _png(im))

    tree.add(
        f"{base}/themerc",
        "\n".join(
            [
                f"active_text_color={t.bone}",
                f"inactive_text_color={s['dim']}",
                f"active_text_shadow_color={s['header']}",
                f"inactive_text_shadow_color={s['win']}",
                f"active_border_color={s['border']}",
                f"inactive_border_color={s['header']}",
                f"active_color_1={s['header']}",
                f"active_color_2={s['header']}",
                f"inactive_color_1={s['win']}",
                f"inactive_color_2={s['win']}",
                "button_offset=0",
                "button_spacing=0",
                "full_width_title=true",
                "frame_border_top=0",
                "maximized_offset=0",
                "show_app_icon=true",
                "title_horizontal_offset=8",
                "title_shadow_active=false",
                "title_shadow_inactive=false",
                "title_vertical_offset_active=0",
                "title_vertical_offset_inactive=0",
                "",
            ]
        ),
    )
    return tree
