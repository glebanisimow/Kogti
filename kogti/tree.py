"""In-memory file tree: lets the build run anywhere (even Windows) and feed both a .deb and a debug dump."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Entry:
    data: bytes | None = None
    mode: int = 0o644
    link: str | None = None


class Tree:
    def __init__(self) -> None:
        self.files: dict[str, Entry] = {}

    @staticmethod
    def _norm(path: str) -> str:
        return path.strip("/").replace("\\", "/")

    def add(self, path: str, data: bytes | str, mode: int = 0o644) -> None:
        if isinstance(data, str):
            data = data.encode("utf-8")
        self.files[self._norm(path)] = Entry(data=data, mode=mode)

    def link(self, path: str, target: str) -> None:
        self.files[self._norm(path)] = Entry(link=target, mode=0o777)

    def get(self, path: str) -> bytes:
        e = self.files[self._norm(path)]
        assert e.data is not None
        return e.data

    def __contains__(self, path: str) -> bool:
        return self._norm(path) in self.files

    def merge(self, other: "Tree") -> None:
        self.files.update(other.files)

    def dirs(self) -> list[str]:
        out: set[str] = set()
        for p in self.files:
            parts = p.split("/")[:-1]
            for i in range(1, len(parts) + 1):
                out.add("/".join(parts[:i]))
        return sorted(out)

    def dump(self, dest: Path) -> None:
        """Write to disk. Symlinks become copies (Windows-safe) when the target is inside the tree."""
        for p, e in sorted(self.files.items()):
            out = dest / p
            out.parent.mkdir(parents=True, exist_ok=True)
            if e.link is not None:
                tgt = (Path(p).parent / e.link).as_posix()
                src = self.files.get(Path(tgt).as_posix())
                if src and src.data is not None:
                    out.write_bytes(src.data)
                continue
            out.write_bytes(e.data or b"")
