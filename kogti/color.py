"""Small colour toolkit: hex <-> rgb, mixing, WCAG contrast."""
from __future__ import annotations

RGB = tuple[int, int, int]


def parse(h: str) -> RGB:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def to_hex(c: RGB) -> str:
    return "#%02X%02X%02X" % tuple(max(0, min(255, round(v))) for v in c)


def mix(a: str, b: str, t: float) -> str:
    """t=0 -> a, t=1 -> b (sRGB, like GTK's mix())."""
    ca, cb = parse(a), parse(b)
    return to_hex(tuple(x * (1 - t) + y * t for x, y in zip(ca, cb)))


def rgba(h: str, alpha: float) -> str:
    r, g, b = parse(h)
    a = ("%.3f" % alpha).rstrip("0").rstrip(".")
    return f"rgba({r}, {g}, {b}, {a})"


def luminance(h: str) -> float:
    def lin(v: int) -> float:
        s = v / 255
        return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

    r, g, b = parse(h)
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def best_fg(bg: str, light: str, dark: str) -> str:
    return light if contrast(bg, light) >= contrast(bg, dark) else dark


def rgb_floats(h: str) -> tuple[float, float, float]:
    r, g, b = parse(h)
    return r / 255, g / 255, b / 255
