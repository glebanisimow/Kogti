"""Load tokens.toml and derive every colour the theme needs from the three brand colours."""
from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import color as C

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Tokens:
    raw: dict
    root: Path = ROOT
    surfaces: dict[str, str] = field(default_factory=dict)

    # ---- identity -------------------------------------------------------
    @property
    def id(self) -> str:
        return self.raw["theme"]["id"]

    @property
    def name(self) -> str:
        return self.raw["theme"]["name"]

    @property
    def version(self) -> str:
        return self.raw["theme"]["version"]

    @property
    def package(self) -> str:
        return f"xfce-{self.id}"

    # ---- brand ----------------------------------------------------------
    @property
    def ink(self) -> str:
        return self.raw["brand"]["ink"].upper()

    @property
    def amber(self) -> str:
        return self.raw["brand"]["amber"].upper()

    @property
    def bone(self) -> str:
        return self.raw["brand"]["bone"].upper()

    @property
    def danger(self) -> str:
        return self.raw["status"]["danger"].upper()

    @property
    def success(self) -> str:
        return self.raw["status"]["success"].upper()

    @property
    def info(self) -> str:
        return self.raw["status"]["info"].upper()

    @property
    def radius(self) -> int:
        return int(self.raw["geometry"]["radius"])

    # ---- derived --------------------------------------------------------
    def __post_init__(self) -> None:
        ink, bone = self.ink, self.bone
        m = lambda t: C.mix(ink, bone, t)  # noqa: E731
        self.surfaces = {
            "view": ink,
            "win": m(0.055),
            "sidebar": m(0.070),
            "header": m(0.090),
            "dialog": m(0.105),
            "thumb": m(0.125),
            "raised": m(0.140),
            "border": m(0.200),
            "dim": C.mix(bone, ink, 0.45),
        }

    @property
    def warning(self) -> str:
        return C.mix(self.amber, self.bone, 0.30)

    def on(self, bg: str) -> str:
        """Readable foreground for a given background (ink or bone)."""
        return C.best_fg(bg, self.bone, self.ink)

    def standalone(self, c: str) -> str:
        """Variant of a status colour usable as *text* on the dark surfaces."""
        return C.mix(c, self.bone, 0.22)

    def accent_ramp(self) -> list[str]:
        a, b, k = self.amber, self.bone, self.ink
        return [C.mix(a, b, 0.45), C.mix(a, b, 0.20), a, C.mix(a, k, 0.15), C.mix(a, k, 0.30)]

    def ansi(self) -> list[str]:
        """16-colour terminal palette."""
        s, ex = self.surfaces, self.raw["ansi_extra"]
        base = [
            C.mix(self.ink, self.bone, 0.16),
            self.danger,
            self.success,
            self.amber,
            self.info,
            ex["magenta"].upper(),
            ex["cyan"].upper(),
            C.mix(self.bone, self.ink, 0.12),
        ]
        bright = [
            C.mix(self.ink, self.bone, 0.38),
            C.mix(self.danger, self.bone, 0.22),
            C.mix(self.success, self.bone, 0.22),
            C.mix(self.amber, self.bone, 0.22),
            C.mix(self.info, self.bone, 0.22),
            C.mix(ex["magenta"], self.bone, 0.22),
            C.mix(ex["cyan"], self.bone, 0.22),
            self.bone,
        ]
        assert len(base + bright) == 16 and s
        return base + bright

    def gtk_named(self) -> dict[str, str]:
        """libadwaita/adw-gtk3 named colours (underscore form) for the dark style."""
        s = self.surfaces
        bone, ink, amber = self.bone, self.ink, self.amber
        shade = lambda a: C.rgba("#000000", a)  # noqa: E731
        warn = self.warning
        d: dict[str, str] = {
            "accent_bg_color": amber,
            "accent_fg_color": ink,
            "accent_color": amber,
            "destructive_bg_color": self.danger,
            "destructive_fg_color": self.on(self.danger),
            "destructive_color": self.standalone(self.danger),
            "success_bg_color": self.success,
            "success_fg_color": self.on(self.success),
            "success_color": self.standalone(self.success),
            "warning_bg_color": warn,
            "warning_fg_color": self.on(warn),
            "warning_color": warn,
            "error_bg_color": self.danger,
            "error_fg_color": self.on(self.danger),
            "error_color": self.standalone(self.danger),
            "window_bg_color": s["win"],
            "window_fg_color": bone,
            "view_bg_color": s["view"],
            "view_fg_color": bone,
            "headerbar_bg_color": s["header"],
            "headerbar_fg_color": bone,
            "headerbar_border_color": bone,
            "headerbar_backdrop_color": s["win"],
            "headerbar_shade_color": shade(0.36),
            "headerbar_darker_shade_color": shade(0.90),
            "sidebar_bg_color": s["sidebar"],
            "sidebar_fg_color": bone,
            "sidebar_backdrop_color": s["win"],
            "sidebar_shade_color": shade(0.25),
            "sidebar_border_color": shade(0.36),
            "secondary_sidebar_bg_color": s["win"],
            "secondary_sidebar_fg_color": bone,
            "secondary_sidebar_backdrop_color": s["win"],
            "secondary_sidebar_shade_color": shade(0.25),
            "secondary_sidebar_border_color": shade(0.36),
            "card_bg_color": C.rgba(bone, 0.055),
            "card_fg_color": bone,
            "card_shade_color": shade(0.36),
            "overview_bg_color": s["view"],
            "overview_fg_color": bone,
            "dialog_bg_color": s["dialog"],
            "dialog_fg_color": bone,
            "popover_bg_color": s["dialog"],
            "popover_fg_color": bone,
            "popover_shade_color": shade(0.25),
            "thumbnail_bg_color": s["thumb"],
            "thumbnail_fg_color": bone,
            "shade_color": shade(0.25),
            "scrollbar_outline_color": shade(0.95),
            "active_toggle_bg_color": C.rgba(bone, 0.12),
            "active_toggle_fg_color": bone,
            "panel_bg_color": ink,
            "panel_fg_color": bone,
        }
        for i, c in enumerate(self.accent_ramp(), start=1):
            d[f"blue_{i}"] = c
        return d


def load(path: Path | None = None) -> Tokens:
    p = path or ROOT / "tokens.toml"
    with open(p, "rb") as f:
        return Tokens(tomllib.load(f), root=p.parent)
