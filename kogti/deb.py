"""Write a .deb without dpkg-deb, so the package builds on any OS."""
from __future__ import annotations

import gzip
import hashlib
import io
import os
import tarfile
from pathlib import Path

from .tree import Tree

EPOCH = int(os.environ.get("SOURCE_DATE_EPOCH", "1767225600"))  # 2026-01-01, reproducible builds


def _tar_gz(entries: list[tuple[str, bytes | None, int, str | None]], dirs: list[str]) -> bytes:
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.GNU_FORMAT) as tf:

        def fix(ti: tarfile.TarInfo) -> tarfile.TarInfo:
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = "root"
            ti.mtime = EPOCH
            return ti

        for d in ["."] + dirs:
            ti = fix(tarfile.TarInfo("./" if d == "." else f"./{d}/"))
            ti.type = tarfile.DIRTYPE
            ti.mode = 0o755
            tf.addfile(ti)
        for name, data, mode, link in entries:
            ti = fix(tarfile.TarInfo(f"./{name}"))
            ti.mode = mode
            if link is not None:
                ti.type = tarfile.SYMTYPE
                ti.linkname = link
                tf.addfile(ti)
            else:
                ti.size = len(data or b"")
                tf.addfile(ti, io.BytesIO(data or b""))
    gz = io.BytesIO()
    with gzip.GzipFile(fileobj=gz, mode="wb", mtime=EPOCH, compresslevel=9) as g:
        g.write(raw.getvalue())
    return gz.getvalue()


def _ar(members: list[tuple[str, bytes]]) -> bytes:
    out = bytearray(b"!<arch>\n")
    for name, data in members:
        hdr = f"{name:<16}{EPOCH:<12}{0:<6}{0:<6}{'100644':<8}{len(data):<10}`\n"
        out += hdr.encode("ascii") + data
        if len(data) % 2:
            out += b"\n"
    return bytes(out)


def build(tree: Tree, control: dict[str, str], scripts: dict[str, str], out: Path) -> Path:
    files = sorted(tree.files.items())
    entries = [(p, e.data, e.mode, e.link) for p, e in files]
    size_kib = sum(len(e.data or b"") for _, e in files) // 1024 + 1

    md5 = "".join(
        f"{hashlib.md5(e.data).hexdigest()}  {p}\n" for p, e in files if e.data is not None and e.link is None
    )
    fields = dict(control)
    fields["Installed-Size"] = str(size_kib)
    ctrl_text = "".join(f"{k}: {v}\n" for k, v in fields.items())
    ctrl_text = ctrl_text.rstrip("\n") + "\n"

    c_entries: list[tuple[str, bytes | None, int, str | None]] = [
        ("control", ctrl_text.encode("utf-8"), 0o644, None),
        ("md5sums", md5.encode("utf-8"), 0o644, None),
    ]
    for name, body in scripts.items():
        c_entries.append((name, body.encode("utf-8"), 0o755, None))

    control_tgz = _tar_gz(c_entries, [])
    data_tgz = _tar_gz(entries, tree.dirs())
    deb = _ar([("debian-binary", b"2.0\n"), ("control.tar.gz", control_tgz), ("data.tar.gz", data_tgz)])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(deb)
    return out
