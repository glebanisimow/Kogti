#!/usr/bin/env python3
"""Build the whole theme from tokens.toml into dist/<package>_<version>_all.deb.

    python build.py            build the .deb
    python build.py --dump     also write the file tree to dist/tree/ for inspection
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from kogti import assets, bases, deb, gtk, icons, system, tokens, xfwm
from kogti.tree import Tree

POSTINST = """#!/bin/sh
set -e
if [ "$1" = "configure" ]; then
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -f -t /usr/share/icons/{name} || true
    fi
fi
exit 0
"""

POSTRM = """#!/bin/sh
set -e
case "$1" in
    remove|purge)
        rm -f /usr/share/icons/{name}/icon-theme.cache
        ;;
esac
exit 0
"""


def build(dump: bool) -> Path:
    t = tokens.load()
    bases.fetch_adw()
    papirus = bases.fetch_papirus()

    tree = Tree()
    avatar_map = assets.avatars(t, tree)
    wall_map = assets.wallpapers(t, tree)
    tree.merge(gtk.build(t, bases.CACHE))
    tree.merge(xfwm.build(t))
    tree.merge(icons.build(t, papirus))
    tree.merge(system.build(t, avatar_map, wall_map))

    control = {
        "Package": t.package,
        "Version": t.version,
        "Architecture": "all",
        "Maintainer": t.raw["theme"]["maintainer"],
        "Depends": "python3, xfconf, papirus-icon-theme",
        "Recommends": "lightdm-gtk-greeter, libglib2.0-bin, pkexec | policykit-1, qt5ct, qt6ct",
        "Section": "x11",
        "Priority": "optional",
        "Description": f"{t.raw['theme']['description']}\n"
        " Complete dark XFCE theme generated from a three-colour palette: GTK3/GTK4,\n"
        " xfwm4 decorations, folder icons, terminal and Qt colours, wallpapers and\n"
        " login screen. Apply it with `kogti-apply`.",
    }
    out = deb.build(
        tree,
        control,
        {"postinst": POSTINST.format(name=t.name), "postrm": POSTRM.format(name=t.name)},
        Path("dist") / f"{t.package}_{t.version}_all.deb",
    )
    if dump:
        dest = Path("dist") / "tree"
        shutil.rmtree(dest, ignore_errors=True)
        tree.dump(dest)
    print(f"{out}  ({out.stat().st_size // 1024} KiB, {len(tree.files)} files)")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", action="store_true", help="also write dist/tree/")
    args = ap.parse_args()
    build(args.dump)
    sys.exit(0)
