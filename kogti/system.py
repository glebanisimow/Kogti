"""Everything that is not a theme proper: terminal scheme, Qt palette, launchers, docs, theme.json, kogti-apply."""
from __future__ import annotations

import json

from . import color as C
from .tokens import Tokens
from .tree import Tree


def terminal_scheme(t: Tokens) -> str:
    return (
        "[Scheme]\n"
        f"Name={t.name}\n"
        f"ColorForeground={t.bone.lower()}\n"
        f"ColorBackground={t.ink.lower()}\n"
        f"ColorCursor={t.amber.lower()}\n"
        "ColorPalette=" + ";".join(c.lower() for c in t.ansi()) + "\n"
    )


def _argb(h: str) -> str:
    return "#ff" + h.lstrip("#").lower()


def qt_scheme(t: Tokens) -> str:
    """qt5ct/qt6ct palette; role order is QPalette's (21 entries)."""
    s = t.surfaces
    btn = s["header"]
    active = [
        t.bone,                      # WindowText
        btn,                         # Button
        C.mix(btn, t.bone, 0.25),    # Light
        C.mix(btn, t.bone, 0.15),    # Midlight
        t.ink,                       # Dark
        s["border"],                 # Mid
        t.bone,                      # Text
        "#FFFFFF",                   # BrightText
        t.bone,                      # ButtonText
        s["view"],                   # Base
        s["win"],                    # Window
        "#000000",                   # Shadow
        t.amber,                     # Highlight
        t.ink,                       # HighlightedText
        t.amber,                     # Link
        C.mix(t.amber, t.bone, 0.4), # LinkVisited
        C.mix(s["view"], t.bone, 0.04),  # AlternateBase
        t.ink,                       # NoRole
        s["dialog"],                 # ToolTipBase
        t.bone,                      # ToolTipText
        s["dim"],                    # PlaceholderText
    ]
    disabled = list(active)
    dim = C.mix(t.bone, t.ink, 0.6)
    for i in (0, 6, 8):
        disabled[i] = dim
    disabled[12] = C.mix(s["win"], t.bone, 0.2)
    disabled[13] = dim

    def row(name: str, cols: list[str]) -> str:
        return f"{name}=" + ", ".join(_argb(c) for c in cols)

    return "[ColorScheme]\n" + "\n".join(
        [row("active_colors", active), row("disabled_colors", disabled), row("inactive_colors", active)]
    ) + "\n"


def launchers(t: Tokens) -> Tree:
    tree = Tree()
    icon = f"{t.id}-menu"
    tree.add(
        f"usr/share/applications/{t.id}-apply.desktop",
        f"[Desktop Entry]\nType=Application\nName=Apply {t.name} theme\n"
        f"Name[ru]=Применить тему {t.name}\n"
        f"Comment=Switch the desktop and the login screen to {t.name}\n"
        f"Comment[ru]=Включить тему {t.name} для рабочего стола и экрана входа\n"
        f"Exec=kogti-apply --system --notify\nIcon={icon}\nTerminal=false\n"
        "Categories=Settings;DesktopSettings;GTK;\n",
    )
    tree.add(
        f"usr/share/applications/{t.id}-revert.desktop",
        f"[Desktop Entry]\nType=Application\nName=Revert {t.name} theme\n"
        f"Name[ru]=Вернуть прежнюю тему\n"
        "Comment=Restore the settings that were active before the theme was applied\n"
        "Comment[ru]=Вернуть настройки, которые были до применения темы\n"
        f"Exec=kogti-apply --revert --system --notify\nIcon={icon}\nTerminal=false\n"
        "Categories=Settings;DesktopSettings;GTK;\n",
    )
    return tree


def docs(t: Tokens) -> Tree:
    tree = Tree()
    d = f"usr/share/doc/{t.package}"
    tree.add(
        f"{d}/README",
        f"{t.name} - XFCE theme (GTK3/GTK4, xfwm4, icons, terminal, Qt, wallpapers, login screen)\n\n"
        f"  kogti-apply              apply for the current user\n"
        f"  kogti-apply --system     ... and for the login screen (one password prompt)\n"
        f"  kogti-apply --revert     undo (add --system for the login screen)\n"
        f"  kogti-apply --list       available wallpapers and avatars\n\n"
        f"Run `kogti-apply --revert` before removing the package.\n",
    )
    tree.add(
        f"{d}/copyright",
        "Design assets (palette, emblems, patterns, avatars): the theme author.\n\n"
        "GTK stylesheets are derived from adw-gtk3 (https://github.com/lassekongo83/adw-gtk3), LGPL-2.1.\n"
        "Folder icons are derived from Papirus (https://github.com/PapirusDevelopmentTeam/papirus-icon-theme), GPL-3.0.\n"
        "Scripts and generator: the theme author.\n",
    )
    return tree


def theme_json(t: Tokens, avatars: dict[str, str], wallpapers: dict[str, str]) -> str:
    s = t.surfaces
    data = {
        "name": t.name,
        "id": t.id,
        "version": t.version,
        "colors": {
            "ink": t.ink,
            "amber": t.amber,
            "bone": t.bone,
            "win": s["win"],
            "header": s["header"],
            "border": s["border"],
            "dim": s["dim"],
        },
        "ansi": t.ansi(),
        "wallpapers": wallpapers,
        "default_wallpaper": t.raw["assets"]["wallpaper_default"],
        "avatars": avatars,
        "avatar_pixmap": f"/usr/share/pixmaps/{t.id}-avatar.png",
        "menu_icon": f"{t.id}-menu",
        "cursor": t.raw["desktop"].get("cursor", ""),
        "font_ui": t.raw["desktop"].get("font_ui", ""),
    }
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def build(t: Tokens, avatars: dict[str, str], wallpapers: dict[str, str]) -> Tree:
    tree = Tree()
    tree.add(f"usr/share/xfce4/terminal/colorschemes/{t.name}.theme", terminal_scheme(t))
    tree.add(f"usr/share/{t.id}/qt/kogti.conf", qt_scheme(t))
    tree.add(f"usr/share/{t.id}/theme.json", theme_json(t, avatars, wallpapers))
    src = (t.root / "src" / "kogti-apply").read_text(encoding="utf-8")
    tree.add("usr/bin/kogti-apply", src, mode=0o755)
    tree.merge(launchers(t))
    tree.merge(docs(t))
    return tree
