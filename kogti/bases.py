"""Pinned upstream bases, downloaded into .cache/ and reduced to what the build needs.

adw-gtk3  - GTK3/GTK4 stylesheet we re-colour (LGPL-2.1)
Papirus   - folder icon shapes we re-colour (GPL-3.0)
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import tarfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / ".cache"

ADW_VERSION = "v6.5"
ADW_SHA256 = "a81780fadfc432be0fc3d89c4ebb41aa28e4f032d42c36f9789c57dd10cfa41c"
ADW_URL = f"https://github.com/lassekongo83/adw-gtk3/releases/download/{ADW_VERSION}/adw-gtk3{ADW_VERSION}.tar.xz"
ADW_ARCHIVE = CACHE / f"adw-gtk3{ADW_VERSION}.tar.xz"
ADW_DIR = CACHE / "adw-gtk3"

PAPIRUS_TAG = "20260801"
PAPIRUS_SHA256 = "7b22c819319b971b0d3f8d99bf3fd5dfa013290d8fb20943c04f6afab826ce39"
PAPIRUS_URL = f"https://api.github.com/repos/PapirusDevelopmentTeam/papirus-icon-theme/tarball/{PAPIRUS_TAG}"
PAPIRUS_ARCHIVE = CACHE / f"papirus-{PAPIRUS_TAG}.tar.gz"
PAPIRUS_SUBSET = CACHE / "papirus_subset.json.gz"

# Folder shapes at 22..64px (blue default + yellow, same geometry) and the flat 16px set of Papirus-Dark.
WANT_FILE = re.compile(
    r"^(?:Papirus/(?:22x22|24x24|32x32|48x48|64x64)/places/(?:folder|user)-(?:blue|yellow)[^/]*"
    r"|Papirus-Dark/16x16/places/[^/]+)\.svg$"
)
WANT_LINK = re.compile(r"^(?:Papirus/[^/]+|Papirus-Dark/16x16)/places/[^/]+\.svg$")
BLUE_TARGET = re.compile(r"(folder|user)-blue")


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _download(url: str, dest: Path, expect: str) -> None:
    if not dest.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        print(f"download {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "xfce-kogti-build"})
        with urllib.request.urlopen(req) as r, open(dest, "wb") as f:
            while chunk := r.read(1 << 20):
                f.write(chunk)
    got = sha256(dest)
    if got != expect:
        raise SystemExit(f"checksum mismatch for {dest.name}: {got} != {expect}")


def fetch_adw() -> Path:
    _download(ADW_URL, ADW_ARCHIVE, ADW_SHA256)
    marker = ADW_DIR / ".extracted"
    if not marker.exists():
        ADW_DIR.mkdir(parents=True, exist_ok=True)
        with tarfile.open(ADW_ARCHIVE) as t:
            for m in t.getmembers():
                if m.isfile() or m.isdir():
                    t.extract(m, ADW_DIR)
        marker.write_text(ADW_VERSION)
    return ADW_DIR / "adw-gtk3-dark"


def fetch_papirus() -> dict:
    if PAPIRUS_SUBSET.exists():
        with gzip.open(PAPIRUS_SUBSET, "rt", encoding="utf-8") as f:
            return json.load(f)
    _download(PAPIRUS_URL, PAPIRUS_ARCHIVE, PAPIRUS_SHA256)
    files: dict[str, str] = {}
    links: dict[str, str] = {}
    with tarfile.open(PAPIRUS_ARCHIVE, "r|gz") as t:
        for m in t:
            rel = m.name.split("/", 1)[1] if "/" in m.name else m.name
            if m.issym():
                if not WANT_LINK.match(rel):
                    continue
                if rel.startswith("Papirus-Dark/") or BLUE_TARGET.search(m.linkname):
                    links[rel] = m.linkname
            elif m.isfile() and WANT_FILE.match(rel):
                files[rel] = t.extractfile(m).read().decode("utf-8")
    data = {"tag": PAPIRUS_TAG, "files": files, "links": links}
    with gzip.open(PAPIRUS_SUBSET, "wt", encoding="utf-8") as f:
        json.dump(data, f)
    return data


def main() -> None:
    fetch_adw()
    d = fetch_papirus()
    print(f"adw-gtk3 {ADW_VERSION} ok; papirus {d['tag']}: {len(d['files'])} files, {len(d['links'])} links")


if __name__ == "__main__":
    main()
