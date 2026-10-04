"""Dev aid: render dist/tree into dist/preview.html (swatches, folders, window frame, wallpapers) for a visual check.

GTK widgets cannot be rendered outside GTK, so they are not part of this page.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kogti import color as C  # noqa: E402
from kogti import tokens  # noqa: E402

T = tokens.load()
TREE = ROOT / "dist" / "tree" / "usr" / "share"
ICONS = TREE / "icons" / T.name
XF = TREE / "themes" / T.name / "xfwm4"
H = int(T.raw["geometry"]["titlebar"])
B = int(T.raw["geometry"]["border"])


def u(p: Path) -> str:
    return p.relative_to(ROOT / "dist").as_posix()


def swatch(name: str, hexv: str, on: str) -> str:
    return (
        f'<div class="sw" style="background:{hexv};color:{on}"><b>{name}</b><br>{hexv}<br>'
        f"{C.contrast(hexv, on):.1f}:1 vs {on}</div>"
    )


def window(state: str, title: str) -> str:
    def px(n: str) -> str:
        return u(XF / n)

    btns = "".join(
        f'<img src="{px(f"{b}-{state}.png")}" width="{H}" height="{H}">'
        for b in ("shade", "stick", "hide", "maximize", "close")
    )
    return f"""
<div class="win">
  <div class="tb" style="height:{H}px">
    <img src="{px(f"top-left-{state}.png")}">
    <div class="tt" style="background:url({px(f"title-3-{state}.png")}) repeat-x;color:{T.bone if state == "active" else T.surfaces["dim"]}">{title}</div>
    <div class="bt">{btns}</div>
    <img src="{px(f"top-right-{state}.png")}">
  </div>
  <div class="body" style="border-left:{B}px solid;border-right:{B}px solid;border-image:none;
       background:{T.surfaces["win"]};box-shadow: inset {B}px 0 0 {T.surfaces["header"]}, inset -{B}px 0 0 {T.surfaces["header"]}">
    <p style="color:{T.bone}">Window content on <code>{T.surfaces["win"]}</code></p>
    <span class="chip" style="background:{T.amber};color:{T.ink}">suggested action</span>
    <span class="chip" style="background:{T.danger};color:{T.on(T.danger)}">destructive</span>
    <span class="chip" style="background:{T.surfaces["raised"]};color:{T.bone}">button</span>
  </div>
</div>"""


def main() -> None:
    s = T.surfaces
    sw = "".join(
        [
            swatch("ink", T.ink, T.bone),
            swatch("amber", T.amber, T.ink),
            swatch("bone", T.bone, T.ink),
            swatch("win", s["win"], T.bone),
            swatch("header", s["header"], T.bone),
            swatch("dialog", s["dialog"], T.bone),
            swatch("raised", s["raised"], T.bone),
            swatch("border", s["border"], T.bone),
            swatch("dim text", s["dim"], s["win"]),
            swatch("danger", T.danger, T.on(T.danger)),
            swatch("success", T.success, T.on(T.success)),
            swatch("info", T.info, T.on(T.info)),
        ]
    )
    names = ["folder", "folder-documents", "folder-music", "folder-download", "folder-pictures", "user-home", "folder-code", "folder-git"]
    big = "".join(
        f'<figure><img src="{u(ICONS / "48x48" / "places" / (n + ".svg"))}" width="48"><figcaption>{n}</figcaption></figure>'
        for n in names
    )
    small = "".join(
        f'<img src="{u(ICONS / "16x16" / "places" / (n + ".svg"))}" width="16"> ' for n in names
    )
    menu = "".join(
        f'<img src="{u(ICONS / f"{z}x{z}" / "apps" / (T.id + "-menu.png"))}" width="{z}"> ' for z in (16, 24, 32, 48, 64)
    )
    walls = "".join(
        f'<figure><img src="{u(TREE / "backgrounds" / T.id / (T.id + "-" + n + ".png"))}" width="300"><figcaption>{n}</figcaption></figure>'
        for n in ("logo", "claws", "tracks", "rows", "teeth")
    )
    avs = "".join(
        f'<img src="{u(TREE / T.id / "avatars" / (n + ".png"))}" width="72"> '
        for n in ("profile", "profile-hex", "profile-split", "axe", "axe-hex", "axe-square")
    )
    html = f"""<!doctype html><meta charset="utf-8"><title>{T.name} preview</title>
<style>
body{{margin:0;padding:24px;background:{s["win"]};color:{T.bone};font:14px/1.4 system-ui,sans-serif}}
h2{{margin:28px 0 10px;color:{T.amber};font-size:15px;letter-spacing:.06em;text-transform:uppercase}}
.row{{display:flex;flex-wrap:wrap;gap:10px}}
.sw{{width:150px;padding:10px;font-size:12px}}
figure{{margin:0;text-align:center;font-size:11px;color:{s["dim"]}}}
.panel{{padding:14px;background:{s["win"]}}}
.panel.v{{background:{s["view"]}}}
.win{{width:520px;margin:0 20px 20px 0;display:inline-block;vertical-align:top}}
.tb{{display:flex;align-items:stretch}}
.tt{{flex:1;display:flex;align-items:center;padding-left:8px;font-size:13px}}
.bt{{display:flex}}
.tb img{{display:block}}
.body{{padding:16px;min-height:90px}}
.chip{{display:inline-block;padding:6px 12px;margin-right:6px;font-size:13px}}
code{{color:{T.amber}}}
</style>
<h2>Palette (WCAG contrast vs label)</h2><div class="row">{sw}</div>
<h2>Folders 48px on window / on view background</h2>
<div class="row"><div class="panel row">{big}</div><div class="panel v row">{big}</div></div>
<h2>Folders 16px (sidebar size)</h2><div class="panel">{small}</div><div class="panel v">{small}</div>
<h2>xfwm4 frame - focused and unfocused</h2>{window("active", "Terminal - kogti")}{window("inactive", "Files")}
<h2>Menu button glyph</h2><div class="panel v">{menu}</div>
<h2>Wallpapers</h2><div class="row">{walls}</div>
<h2>Avatars</h2><div class="panel v">{avs}</div>
"""
    out = ROOT / "dist" / "preview.html"
    out.write_text(html, encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
