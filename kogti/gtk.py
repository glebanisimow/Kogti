"""GTK3 + GTK4 theme: adw-gtk3-dark with our palette, sharp corners and a few XFCE-specific rules."""
from __future__ import annotations

import re
from pathlib import Path

from . import color as C
from .tokens import Tokens
from .tree import Tree

DEFINE = re.compile(r"^@define-color\s+(\S+)\s+(.*);\s*$")
RADIUS = re.compile(
    r"((?:-gtk-outline|border(?:-(?:top|bottom)-(?:left|right))?)-radius\s*:\s*)([^;}]+)"
)
PX = re.compile(r"-?\d*\.?\d+px$")


def patch_named_colors(css: str, colors: dict[str, str]) -> str:
    """Replace values of existing @define-color lines; add the missing ones after the header block."""
    lines = css.split("\n")
    seen: set[str] = set()
    last_define = -1
    for i, line in enumerate(lines[:400]):
        m = DEFINE.match(line)
        if not m:
            continue
        last_define = i
        name, val = m.group(1), m.group(2).strip()
        seen.add(name)
        if name in colors and val != f"@{name}":
            lines[i] = f"@define-color {name} {colors[name]};"
    missing = [f"@define-color {n} {v};" for n, v in colors.items() if n not in seen]
    if missing and last_define >= 0:
        lines[last_define + 1 : last_define + 1] = missing
    return "\n".join(lines)


def clamp_radius(css: str, px: int) -> str:
    """Square the UI: every px radius above `px` becomes `px`. %, 0 and var() are left alone (radios stay round)."""

    def fix(m: re.Match) -> str:
        parts = m.group(2).split()
        out = []
        for p in parts:
            if PX.match(p) and float(p[:-2]) > px:
                p = f"{px}px"
            out.append(p)
        return m.group(1) + " ".join(out)

    return RADIUS.sub(fix, css)


def named_colors_block(t: Tokens) -> str:
    """Colours for ~/.config/gtk-4.0/gtk.css and for the theme's own gtk-4.0 sheet.

    libadwaita >= 1.6 reads CSS variables, older stylesheets read @define-color: emit both.
    """
    d = t.gtk_named()
    s = t.surfaces
    compat = {
        "theme_bg_color": d["window_bg_color"],
        "theme_fg_color": d["window_fg_color"],
        "theme_base_color": d["view_bg_color"],
        "theme_text_color": d["view_fg_color"],
        "theme_selected_bg_color": d["accent_bg_color"],
        "theme_selected_fg_color": d["accent_fg_color"],
        "insensitive_bg_color": C.mix(s["win"], s["view"], 0.4),
        "insensitive_fg_color": C.rgba(t.bone, 0.5),
        "insensitive_base_color": d["view_bg_color"],
        "theme_unfocused_bg_color": d["window_bg_color"],
        "theme_unfocused_fg_color": d["window_fg_color"],
        "theme_unfocused_base_color": d["view_bg_color"],
        "theme_unfocused_text_color": d["view_fg_color"],
        "theme_unfocused_selected_bg_color": d["accent_bg_color"],
        "theme_unfocused_selected_fg_color": d["accent_fg_color"],
    }
    out = [f"/* {t.name}: generated from tokens.toml - do not edit */"]
    out += [f"@define-color {k} {v};" for k, v in {**d, **compat}.items()]
    out.append(":root {")
    out += [f"  --{k.replace('_', '-')}: {v};" for k, v in d.items()]
    out.append(f"  --window-radius: {t.radius}px;")
    out.append("}")
    return "\n".join(out) + "\n"


def shape_block(t: Tokens, gtk4: bool) -> str:
    """Small hand-written rules on top of the re-coloured base."""
    acc = "var(--accent-bg-color)" if gtk4 else "@accent_bg_color"
    fg = "var(--accent-fg-color)" if gtk4 else "@accent_fg_color"
    line = t.raw["geometry"]["accent_line"]
    return f"""
/* ---- {t.name}: shape and accents ---- */
headerbar:not(:backdrop),
.titlebar:not(:backdrop) {{
  box-shadow: inset 0 -{line}px {acc};
}}

.xfce4-panel.background,
XfcePanelWindow {{
  background-color: {t.ink};
  color: {t.bone};
}}
.xfce4-panel button {{
  border-radius: 0;
  border-color: transparent;
  background-image: none;
  box-shadow: none;
}}
.xfce4-panel button:hover {{
  background-color: {C.rgba(t.amber, 0.18)};
}}
.xfce4-panel button:checked,
.xfce4-panel button:active {{
  background-color: {acc};
  color: {fg};
}}
"""


def build(t: Tokens, cache: Path) -> Tree:
    src = cache / "adw-gtk3" / "adw-gtk3-dark"
    if not src.exists():
        raise SystemExit("adw-gtk3 not fetched: run `python tools/fetch_bases.py`")
    tree = Tree()
    base = f"usr/share/themes/{t.name}"
    colors = t.gtk_named()
    r = t.radius

    tree.add(
        f"{base}/index.theme",
        f"[Desktop Entry]\nType=X-GNOME-Metatheme\nName={t.name}\nComment={t.raw['theme']['description']}\n"
        f"Encoding=UTF-8\n\n[X-GNOME-Metatheme]\nGtkTheme={t.name}\nMetacityTheme={t.name}\nIconTheme={t.name}\n",
    )

    # ---- GTK3 --------------------------------------------------------------
    gtk3 = (src / "gtk-3.0" / "gtk.css").read_text(encoding="utf-8")
    gtk3 = patch_named_colors(gtk3, colors)
    gtk3 = clamp_radius(gtk3, r) + shape_block(t, gtk4=False)
    tree.add(f"{base}/gtk-3.0/gtk.css", gtk3)
    tree.add(f"{base}/gtk-3.0/gtk-dark.css", gtk3)
    _copy_assets(tree, src / "gtk-3.0" / "assets", f"{base}/gtk-3.0/assets")

    # ---- GTK4 --------------------------------------------------------------
    lib = (src / "gtk-4.0" / "libadwaita.css").read_text(encoding="utf-8")
    lib = patch_named_colors(lib, colors)
    lib = clamp_radius(lib, r)
    tweaks = (src / "gtk-4.0" / "libadwaita-tweaks.css").read_text(encoding="utf-8")
    tweaks = re.sub(r"^@define-color accent_(?:bg|fg)_color .*$", "", tweaks, flags=re.M)
    tweaks = tweaks.replace("--accent-bg-color: var(--accent-blue);", "")
    tweaks = clamp_radius(tweaks, r)
    colors4 = named_colors_block(t)
    tree.add(f"{base}/gtk-4.0/libadwaita.css", lib)
    tree.add(f"{base}/gtk-4.0/libadwaita-tweaks.css", tweaks)
    tree.add(f"{base}/gtk-4.0/{t.id}-colors.css", colors4)
    tree.add(f"{base}/gtk-4.0/{t.id}-shape.css", shape_block(t, gtk4=True))
    sheet = (
        "@import url('libadwaita.css');\n"
        "@import url('libadwaita-tweaks.css');\n"
        f"@import url('{t.id}-colors.css');\n"
        f"@import url('{t.id}-shape.css');\n"
    )
    tree.add(f"{base}/gtk-4.0/gtk.css", sheet)
    tree.add(f"{base}/gtk-4.0/gtk-dark.css", sheet)
    _copy_assets(tree, src / "gtk-4.0" / "assets", f"{base}/gtk-4.0/assets")

    # Shipped separately so `kogti-apply` can theme libadwaita apps (they ignore the GTK theme).
    libadwaita_user = colors4 + libadwaita_radius_block(t) + shape_block(t, gtk4=True)
    tree.add(f"usr/share/{t.id}/gtk-4.0-user.css", libadwaita_user)
    return tree


def libadwaita_radius_block(t: Tokens) -> str:
    r = t.radius
    return f"""
/* ---- sharp geometry for libadwaita apps ---- */
button, entry, spinbutton, dropdown > button, searchbar > revealer > box,
.card, .boxed-list, .pill, .toolbar-view, popover > contents, popover.menu > contents,
toast, tooltip > box, progressbar > trough, progressbar > trough > progress,
scale > trough, scale > trough > highlight, switch, switch > slider,
notebook > header > tabs > tab, tabbar tab, row, .navigation-sidebar > row {{
  border-radius: {r}px;
}}
"""


def _copy_assets(tree: Tree, src: Path, dest: str) -> None:
    if not src.exists():
        return
    for p in sorted(src.rglob("*")):
        if p.is_file():
            tree.add(f"{dest}/{p.relative_to(src).as_posix()}", p.read_bytes())
