"""Static + behavioural checks for the built package. Exit code 1 if anything fails.

    python build.py && python tools/verify.py

What this can and cannot prove: it checks file structure, colour maths, XML validity and runs the apply/revert
logic against a fake xfconf. It cannot render GTK or talk to a real XFCE session - that needs a real machine.
"""
from __future__ import annotations

import gzip
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import re
import shutil
import sys
import tarfile
import tempfile
import types
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from kogti import color as C  # noqa: E402
from kogti import tokens  # noqa: E402

T = tokens.load()
DEB = ROOT / "dist" / f"{T.package}_{T.version}_all.deb"
results: list[tuple[bool, str]] = []


def check(ok: bool, msg: str) -> None:
    results.append((bool(ok), msg))
    print(("PASS  " if ok else "FAIL  ") + msg)


# ------------------------------------------------------------------ deb -----
def read_deb() -> tuple[dict[str, str], dict[str, bytes], dict[str, str]]:
    raw = DEB.read_bytes()
    check(raw.startswith(b"!<arch>\n"), "deb: ar magic")
    pos, members = 8, {}
    while pos < len(raw):
        hdr = raw[pos : pos + 60]
        name, size = hdr[:16].decode().strip(), int(hdr[48:58].decode())
        members[name] = raw[pos + 60 : pos + 60 + size]
        pos += 60 + size + (size % 2)
    check(list(members) == ["debian-binary", "control.tar.gz", "data.tar.gz"], "deb: member order is dpkg-compatible")
    check(members["debian-binary"] == b"2.0\n", "deb: format 2.0")
    ctl = tarfile.open(fileobj=io.BytesIO(members["control.tar.gz"]), mode="r:gz")
    control = ctl.extractfile("./control").read().decode()
    fields = dict(re.findall(r"^([A-Za-z-]+): (.*)$", control, re.M))
    scripts = {n: ctl.extractfile(f"./{n}").read().decode() for n in ("postinst", "postrm")}
    md5 = ctl.extractfile("./md5sums").read().decode()
    data = tarfile.open(fileobj=io.BytesIO(members["data.tar.gz"]), mode="r:gz")
    files = {m.name[2:]: data.extractfile(m).read() for m in data.getmembers() if m.isfile()}
    modes = {m.name[2:]: m.mode for m in data.getmembers() if m.isfile()}
    bad = [p for line in md5.splitlines() for h, p in [line.split("  ", 1)] if hashlib.md5(files[p]).hexdigest() != h]
    check(not bad and len(md5.splitlines()) == len(files), f"deb: md5sums match all {len(files)} files")
    check(all(m.uid == 0 and m.gid == 0 for m in data.getmembers()), "deb: every entry owned by root")
    check(modes["usr/bin/kogti-apply"] == 0o755, "deb: kogti-apply is executable")
    check(fields.get("Package") == T.package and fields.get("Architecture") == "all", "deb: control Package/Architecture")
    check(re.fullmatch(r"[0-9]+(\.[0-9]+)*", fields.get("Version", "")) is not None, "deb: Version is valid")
    check("papirus-icon-theme" in fields.get("Depends", ""), "deb: depends on papirus-icon-theme")
    check(all(s.startswith("#!/bin/sh") for s in scripts.values()), "deb: maintainer scripts are POSIX sh")
    return fields, files, modes  # type: ignore[return-value]


# ------------------------------------------------------------------ css -----
def check_css(files: dict[str, bytes]) -> None:
    base = f"usr/share/themes/{T.name}"
    for rel in ("gtk-3.0/gtk.css", "gtk-3.0/gtk-dark.css", "gtk-4.0/libadwaita.css", f"gtk-4.0/{T.id}-colors.css", "gtk-4.0/gtk.css"):
        css = files[f"{base}/{rel}"].decode()
        stripped = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
        check(stripped.count("{") == stripped.count("}"), f"css: braces balanced in {rel}")
    g3 = files[f"{base}/gtk-3.0/gtk.css"].decode()
    check(f"@define-color accent_bg_color {T.amber};" in g3, "gtk3: accent is amber")
    check(f"@define-color window_bg_color {T.surfaces['win']};" in g3, "gtk3: window background replaced")
    check("#3584e4" not in g3.lower() and "#222226" not in g3.lower(), "gtk3: no leftover adwaita blue / grey literals")
    big = [m for m in re.findall(r"border(?:-[a-z]+)*-radius:\s*([^;]+);", g3) for v in re.findall(r"([\d.]+)px", m) if float(v) > T.radius]
    check(not big, f"gtk3: all px radii <= {T.radius}px (found {len(big)} above)")
    g4 = files[f"{base}/gtk-4.0/libadwaita.css"].decode()
    check(f"@define-color accent_bg_color {T.amber};" in g4, "gtk4: accent is amber")
    tw = files[f"{base}/gtk-4.0/libadwaita-tweaks.css"].decode()
    check("accent_bg_color @blue_3" not in tw and "--accent-bg-color: var(--accent-blue)" not in tw, "gtk4: tweaks no longer force blue accent")
    colors = files[f"{base}/gtk-4.0/{T.id}-colors.css"].decode()
    for var in ("--accent-bg-color", "--window-bg-color", "--headerbar-bg-color", "--view-bg-color", "--popover-bg-color", "--sidebar-bg-color"):
        check(f"{var}:" in colors, f"gtk4: libadwaita variable {var} set")
    check(f"usr/share/{T.id}/gtk-4.0-user.css" in files, "gtk4: user-level libadwaita override shipped")
    imports = re.findall(r"@import url\('([^']+)'\)", files[f"{base}/gtk-4.0/gtk.css"].decode())
    check(all(f"{base}/gtk-4.0/{i}" in files for i in imports), f"gtk4: all {len(imports)} @imports resolve")
    refs = set(re.findall(r"url\(['\"]?assets/([^'\")]+)", g3))
    check(all(f"{base}/gtk-3.0/assets/{r}" in files for r in refs), f"gtk3: all {len(refs)} referenced assets exist")


def check_contrast() -> None:
    n = T.gtk_named()
    s = T.surfaces
    pairs = [
        ("text on window", T.bone, s["win"], 12),
        ("text on header", T.bone, s["header"], 12),
        ("text on popover", T.bone, s["dialog"], 11),
        ("ink on amber (accent button)", n["accent_fg_color"], n["accent_bg_color"], 8),
        ("amber text on window", T.amber, s["win"], 7),
        ("dim text on window", s["dim"], s["win"], 4.5),
        ("danger button text", n["destructive_fg_color"], n["destructive_bg_color"], 4.5),
        ("success button text", n["success_fg_color"], n["success_bg_color"], 4.5),
        ("warning button text", n["warning_fg_color"], n["warning_bg_color"], 4.5),
        ("danger as text on window", n["destructive_color"], s["win"], 4.5),
        ("terminal red on background", T.danger, T.ink, 4.5),
        ("terminal bright black (comments) on background", T.ansi()[8], T.ink, 3.0),
    ]
    for name, fg, bg, need in pairs:
        r = C.contrast(fg, bg)
        check(r >= need, f"contrast {name}: {r:.1f}:1 (need {need})")


# ------------------------------------------------------------------ xfwm ----
def check_xfwm(files: dict[str, bytes]) -> None:
    base = f"usr/share/themes/{T.name}/xfwm4"
    H, B = int(T.raw["geometry"]["titlebar"]), int(T.raw["geometry"]["border"])
    need = ["themerc"]
    for st in ("active", "inactive"):
        need += [f"title-{i}-{st}.png" for i in range(1, 6)]
        need += [f"{k}-{st}.png" for k in ("top-left", "top-right", "left", "right", "bottom", "bottom-left", "bottom-right")]
    for g in ("close", "hide", "maximize", "maximize-toggled", "menu", "shade", "shade-toggled", "stick", "stick-toggled"):
        need += [f"{g}-{st}.png" for st in ("active", "inactive", "prelight", "pressed")]
    missing = [n for n in need if f"{base}/{n}" not in files]
    check(not missing, f"xfwm4: all {len(need)} required files present {missing[:3]}")

    def size(n: str) -> tuple[int, int]:
        return Image.open(io.BytesIO(files[f"{base}/{n}"])).size

    check(all(size(f"title-{i}-active.png")[1] == H for i in range(1, 6)), f"xfwm4: title tiles are {H}px high")
    check(size("top-left-active.png") == (B, H) and size("top-right-active.png") == (B, H), "xfwm4: top corners match title height")
    check(size("left-active.png")[0] == B and size("bottom-active.png")[1] == B, "xfwm4: side borders are the configured width")
    check(all(size(f"close-{st}.png") == (H, H) for st in ("active", "inactive", "prelight", "pressed")), "xfwm4: buttons are square and title-high")
    rc = files[f"{base}/themerc"].decode()
    check("full_width_title=true" in rc and f"active_text_color={T.bone}" in rc, "xfwm4: themerc has title colours")


# ------------------------------------------------------------------ icons ---
def check_icons(files: dict[str, bytes]) -> None:
    root = f"usr/share/icons/{T.name}"
    svgs = {p: d for p, d in files.items() if p.startswith(root) and p.endswith(".svg")}
    bad = []
    for p, d in svgs.items():
        try:
            ET.fromstring(d)
        except ET.ParseError:
            bad.append(p)
    check(not bad, f"icons: all {len(svgs)} SVGs are well-formed XML {bad[:2]}")
    for sz in (22, 24, 32, 48, 64):
        d = f"{root}/{sz}x{sz}"
        check(all(f"{d}/{x}" in files for x in ("places/folder.svg", "places/user-home.svg", "places/folder-documents.svg", "mimetypes/inode-directory.svg")),
              f"icons: core folder names at {sz}px")
        blue = [p for p in svgs if p.startswith(f"{d}/places/") and b"#5294e2" in svgs[p].lower()]
        check(not blue, f"icons: no Papirus blue left at {sz}px")
    check(f"{root}/16x16/places/folder.svg" in files and f"{root}/16x16/mimetypes/inode-directory.svg" in files, "icons: 16px folder + inode-directory")
    idx = files[f"{root}/index.theme"].decode()
    dirs = re.search(r"^Directories=(.*)$", idx, re.M).group(1).split(",")
    check(all(f"[{d}]" in idx for d in dirs), f"icons: index.theme declares all {len(dirs)} directories")
    used = {str(Path(p).parent.relative_to(root)).replace("\\", "/") for p in files if p.startswith(root) and not p.endswith("index.theme")}
    check(used <= set(dirs), f"icons: no file lives in an undeclared directory {sorted(used - set(dirs))[:3]}")
    check(f"{root}/48x48/apps/{T.id}-menu.png" in files, "icons: menu glyph installed")


# ------------------------------------------------------------------ data ----
def check_data(files: dict[str, bytes]) -> dict:
    tj = json.loads(files[f"usr/share/{T.id}/theme.json"])
    paths = list(tj["wallpapers"].values()) + [v for v in tj["avatars"].values()] + [tj["avatar_pixmap"]]
    check(all(p.lstrip("/") in files for p in paths), f"data: all {len(paths)} wallpaper/avatar paths in theme.json exist")
    check(tj["default_wallpaper"] in tj["wallpapers"], "data: default wallpaper is defined")
    check(len(tj["ansi"]) == 16, "data: 16 ANSI colours")
    qt = files[f"usr/share/{T.id}/qt/kogti.conf"].decode()
    counts = [len(l.split("=", 1)[1].split(",")) for l in qt.splitlines() if "_colors=" in l]
    check(counts == [21, 21, 21], f"data: Qt palette has 21 roles x3 ({counts})")
    for k, p in tj["wallpapers"].items():
        im = Image.open(io.BytesIO(files[p.lstrip("/")]))
        check(im.size == (3840, 2160), f"data: wallpaper {k} is 3840x2160") if k == "logo" else None
    ts = files[f"usr/share/xfce4/terminal/colorschemes/{T.name}.theme"].decode()
    check(ts.count(";") == 15, "data: terminal scheme has 16 palette colours")
    return tj


# ------------------------------------------------------------------ apply ---
def load_apply(data_dir: Path, home: Path, fake: Path):
    os.environ.update(KOGTI_DATA=str(data_dir), HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"),
                      XDG_STATE_HOME=str(home / ".local" / "state"), KOGTI_FAKE_XFCONF=str(fake))
    if not hasattr(os, "geteuid"):
        os.geteuid = lambda: 1000  # type: ignore[attr-defined]
        os.getuid = lambda: 1000  # type: ignore[attr-defined]
    sys.modules.setdefault("pwd", types.SimpleNamespace(getpwuid=lambda uid: types.SimpleNamespace(pw_name="tester", struct_passwd=None)))
    loader = importlib.machinery.SourceFileLoader("kogti_apply", str(ROOT / "src" / "kogti-apply"))
    spec = importlib.util.spec_from_loader("kogti_apply", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


def check_apply(files: dict[str, bytes], tj: dict) -> None:
    src = (ROOT / "src" / "kogti-apply").read_text(encoding="utf-8")
    compile(src, "kogti-apply", "exec")
    check(src.startswith("#!/usr/bin/env python3\n") and "\r" not in src, "apply: kogti-apply compiles, LF line endings, python3 shebang")

    tmp = Path(tempfile.mkdtemp(prefix="kogti-verify-"))
    try:
        stage = tmp / "root"
        for p, d in files.items():
            (stage / p).parent.mkdir(parents=True, exist_ok=True)
            (stage / p).write_bytes(d)
        data = stage / "usr" / "share" / T.id
        fix = lambda s: str(stage / s.lstrip("/"))  # noqa: E731
        tj2 = dict(tj)
        tj2["wallpapers"] = {k: fix(v) for k, v in tj["wallpapers"].items()}
        tj2["avatars"] = {k: fix(v) for k, v in tj["avatars"].items()}
        tj2["avatar_pixmap"] = fix(tj["avatar_pixmap"])
        (data / "theme.json").write_text(json.dumps(tj2), encoding="utf-8")

        home = tmp / "home"
        (home / ".config" / "gtk-4.0").mkdir(parents=True)
        (home / ".config" / "gtk-4.0" / "gtk.css").write_text("/* user rule */\nwindow { margin: 0; }\n", encoding="utf-8")
        (home / ".config" / "gtk-3.0").mkdir(parents=True)
        (home / ".config" / "gtk-3.0" / "settings.ini").write_text("[Settings]\n# keep me\ngtk-font-name=Sans 10\ngtk-theme-name=Adwaita\n", encoding="utf-8")
        (home / ".config" / "xfce4" / "terminal").mkdir(parents=True)
        (home / ".config" / "xfce4" / "terminal" / "terminalrc").write_text("[Configuration]\nFontName=Mono 11\nColorForeground=#ffffff\n", encoding="utf-8")
        (home / ".face").write_bytes(b"old-face")

        fake = tmp / "xfconf.json"
        initial = {
            "xsettings|/Net/ThemeName": ["Adwaita-dark"],
            "xsettings|/Net/IconThemeName": ["Papirus"],
            "xfwm4|/general/theme": ["Default"],
            "xfce4-desktop|/backdrop/screen0/monitorHDMI-1/workspace0/last-image": ["/usr/share/backgrounds/old.jpg"],
            "xfce4-desktop|/backdrop/screen0/monitorHDMI-1/workspace0/image-style": ["3"],
            "xfce4-panel|/panels/panel-1/position": ["p=6"],
            "xfce4-panel|/panels/panel-1/background-style": ["0"],
            "xfce4-panel|/panels/panel-2/position": ["p=8"],
            "xfce4-panel|/plugins/plugin-1": ["whiskermenu"],
            "xfce4-panel|/plugins/plugin-2": ["tasklist"],
        }
        fake.write_text(json.dumps(initial), encoding="utf-8")

        mod = load_apply(data, home, fake)
        real_which = mod.which
        mod.which = lambda prog: prog in ("qt5ct",) or (False if prog in ("gsettings", "xfce4-panel", "xfdesktop", "notify-send") else real_which(prog))
        mod.restart_shell = lambda: None

        def run_main(*argv: str) -> int:
            sys.argv = ["kogti-apply", *argv]
            mod.DRY = False
            return mod.main()

        buf = io.StringIO()
        old_out, sys.stdout = sys.stdout, buf
        try:
            rc = run_main()
            state = json.loads(fake.read_text())

            def read(rel: str) -> str:
                p = home / rel
                return p.read_text(encoding="utf-8") if p.exists() else ""

            snap = {
                rel: read(rel)
                for rel in (
                    ".config/xfce4/panel/whiskermenu-1.rc",
                    ".config/xfce4/panel/whiskermenu-2.rc",
                    ".config/xfce4/terminal/terminalrc",
                    ".config/gtk-3.0/settings.ini",
                    ".config/qt5ct/colors/kogti.conf",
                    ".config/qt5ct/qt5ct.conf",
                    ".xsessionrc",
                )
            }
            rc2 = run_main()
            state2 = json.loads(fake.read_text())
            gtk_css_twice = (home / ".config/gtk-4.0/gtk.css").read_text(encoding="utf-8")
            rc3 = run_main("--revert")
            reverted = json.loads(fake.read_text())
            rc4 = run_main("--dry-run")
        finally:
            sys.stdout = old_out

        check(rc == 0 and rc2 == 0 and rc3 == 0 and rc4 == 0, "apply: apply, re-apply, revert and dry-run all exit 0")
        check(state["xsettings|/Net/ThemeName"] == [T.name] and state["xfwm4|/general/theme"] == [T.name], "apply: GTK + window theme set")
        wp = state["xfce4-desktop|/backdrop/screen0/monitorHDMI-1/workspace0/last-image"][0]
        check(wp.endswith(f"{T.id}-{tj['default_wallpaper']}.png") and Path(wp).exists(), "apply: wallpaper set to an existing file")
        check(state["xfce4-panel|/panels/panel-1/background-style"] == ["1"] and state["xfce4-panel|/panels/panel-2/background-style"] == ["1"],
              "apply: every panel gets a solid background")
        check(len(state["xfce4-panel|/panels/panel-1/background-rgba"]) == 4, "apply: panel colour is an RGBA array")
        check(f"button-icon={T.id}-menu" in snap[".config/xfce4/panel/whiskermenu-1.rc"], "apply: Whisker menu icon set on the whiskermenu plugin")
        check(snap[".config/xfce4/panel/whiskermenu-2.rc"] == "", "apply: other plugins untouched")
        tr = snap[".config/xfce4/terminal/terminalrc"]
        check("FontName=Mono 11" in tr and f"ColorBackground={T.ink}" in tr and "ColorPalette=" in tr and tr.count("ColorForeground=") == 1,
              "apply: terminal colours set once, font preserved")
        si = snap[".config/gtk-3.0/settings.ini"]
        check("# keep me" in si and "gtk-font-name=Sans 10" in si and f"gtk-theme-name={T.name}" in si and si.count("gtk-theme-name") == 1,
              "apply: settings.ini comments and other keys preserved, theme replaced in place")
        check(state2 == state, "apply: second run is idempotent")
        check(gtk_css_twice.count(mod.BEGIN) == 1 and "/* user rule */" in gtk_css_twice, "apply: gtk.css has exactly one managed block, user rules kept")
        qt = snap[".config/qt5ct/qt5ct.conf"]
        check(snap[".config/qt5ct/colors/kogti.conf"].startswith("[ColorScheme]") and "style=Fusion" in qt and "QT_QPA_PLATFORMTHEME=qt5ct" in snap[".xsessionrc"],
              "apply: Qt palette, qt5ct config and session variable written")
        check(reverted == initial, "revert: xfconf state identical to the original")
        check((home / ".face").read_bytes() == b"old-face", "revert: avatar restored")
        check("# keep me" in (home / ".config/gtk-3.0/settings.ini").read_text() and "Adwaita" in (home / ".config/gtk-3.0/settings.ini").read_text(),
              "revert: settings.ini restored")
        check((home / ".config/gtk-4.0/gtk.css").read_text() == "/* user rule */\nwindow { margin: 0; }\n", "revert: gtk.css back to the user's own rules")
        check(not (home / ".config/xfce4/panel/whiskermenu-1.rc").exists() and not (home / ".xsessionrc").exists(), "revert: files we created are removed")
        check("xfconf-query" in buf.getvalue() or "write" in buf.getvalue(), "apply: dry-run prints its plan")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    if not DEB.exists():
        print("run `python build.py` first")
        return 2
    _, files, _ = read_deb()
    check_css(files)
    check_contrast()
    check_xfwm(files)
    check_icons(files)
    tj = check_data(files)
    check_apply(files, tj)
    failed = [m for ok, m in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
