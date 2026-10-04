"""Icon theme: Papirus folder shapes re-coloured to the brand palette, plus the menu glyph.

Only folders and user-dirs are overridden; everything else is inherited from Papirus-Dark.
"""
from __future__ import annotations

import posixpath
import re

from . import assets
from . import color as C
from .tokens import Tokens
from .tree import Tree

FOLDER_SIZES = (22, 24, 32, 48, 64)
FLAT_SIZE = 16


def recolor_map(t: Tokens) -> dict[str, str]:
    """Papirus 'blue' folder palette -> brand palette (lower-case keys)."""
    return {
        "#5294e2": t.amber,                          # folder front
        "#4877b1": C.mix(t.amber, t.ink, 0.22),      # folder back
        "#1d344f": t.ink,                            # glyph on the folder front
        "#ffffff": t.bone,                           # glyph
        "#e4e4e4": C.mix(t.bone, t.ink, 0.10),       # paper sheet inside the folder
    }


def recolor_flat(t: Tokens) -> dict[str, str]:
    """16px Papirus-Dark symbolic set: tint the text colour and highlight with the accent."""
    return {
        "#dfdfdf": t.amber,
        "#4285f4": t.amber,
        "#5294e2": t.amber,
    }


def _apply(svg: str, mapping: dict[str, str]) -> str:
    def sub(m: re.Match) -> str:
        return mapping.get(m.group(0).lower(), m.group(0))

    return re.sub(r"#[0-9a-fA-F]{6}\b", sub, svg)


def _resolve(name: str, files: dict[str, str], links: dict[str, str]) -> str | None:
    seen = 0
    while name in links and seen < 8:
        name = posixpath.basename(links[name])
        seen += 1
    return files.get(name)


def build(t: Tokens, papirus: dict) -> Tree:
    tree = Tree()
    root = f"usr/share/icons/{t.name}"
    dirs: list[tuple[str, int, str]] = []  # (dir, size, context)

    def emit(size_dir: str, size: int, ctx_dir: str, ctx: str, name: str, svg: str) -> None:
        tree.add(f"{root}/{size_dir}/{ctx_dir}/{name}", svg)
        key = (f"{size_dir}/{ctx_dir}", size, ctx)
        if key not in dirs:
            dirs.append(key)

    maps = {"folder": recolor_map(t), "flat": recolor_flat(t)}

    for size in FOLDER_SIZES:
        sd = f"{size}x{size}"
        prefix = f"Papirus/{sd}/places/"
        files = {p[len(prefix):]: s for p, s in papirus["files"].items() if p.startswith(prefix)}
        links = {p[len(prefix):]: l for p, l in papirus["links"].items() if p.startswith(prefix)}
        names = {n for n in links if "bluegrey" not in n}
        names |= {n for n in files if re.match(r"(folder|user)-blue(?!grey)", n)}
        for name in sorted(names):
            svg = _resolve(name, files, links)
            if svg is None:
                continue
            svg = _apply(svg, maps["folder"])
            emit(sd, size, "places", "Places", name, svg)
            if name == "folder.svg":
                emit(sd, size, "mimetypes", "MimeTypes", "inode-directory.svg", svg)

    sd = f"{FLAT_SIZE}x{FLAT_SIZE}"
    prefix = f"Papirus-Dark/{sd}/places/"
    files = {p[len(prefix):]: s for p, s in papirus["files"].items() if p.startswith(prefix)}
    links = {p[len(prefix):]: l for p, l in papirus["links"].items() if p.startswith(prefix)}
    for name in sorted(set(files) | set(links)):
        svg = _resolve(name, files, links)
        if svg is None:
            continue
        svg = _apply(svg, maps["flat"])
        emit(sd, FLAT_SIZE, "places", "Places", name, svg)
        if name == "folder.svg":
            emit(sd, FLAT_SIZE, "mimetypes", "MimeTypes", "inode-directory.svg", svg)

    assets.menu_icons(t, tree)
    for size in assets.ICON_SIZES:
        for ctx_dir, ctx in (("apps", "Applications"), ("places", "Places")):
            key = (f"{size}x{size}/{ctx_dir}", size, ctx)
            if key not in dirs:
                dirs.append(key)

    dirs.sort(key=lambda d: (d[1], d[0]))
    lines = [
        "[Icon Theme]",
        f"Name={t.name}",
        f"Comment={t.raw['theme']['description']}",
        "Inherits=Papirus-Dark,Papirus,hicolor",
        "Directories=" + ",".join(d[0] for d in dirs),
        "",
    ]
    for d, size, ctx in dirs:
        lines += [f"[{d}]", f"Size={size}", f"Context={ctx}", "Type=Fixed", ""]
    tree.add(f"{root}/index.theme", "\n".join(lines))
    return tree
