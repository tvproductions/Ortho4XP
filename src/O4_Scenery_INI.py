import os
from dataclasses import dataclass


@dataclass
class SceneryEntry:
    path: str
    disabled: bool = False


class SceneryINI:
    def __init__(self, path: str = ""):
        self.path = path
        self._entries: list[SceneryEntry] = []

    def read(self, path: str | None = None) -> None:
        if path:
            self.path = path
        self._entries = []
        if not self.path or not os.path.isfile(self.path):
            return
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("SCENERY_PACK "):
                    raw_path = stripped[len("SCENERY_PACK ") :]
                    self._entries.append(SceneryEntry(path=raw_path, disabled=False))
                elif stripped.startswith("SCENERY_PACK_DISABLED "):
                    raw_path = stripped[len("SCENERY_PACK_DISABLED ") :]
                    self._entries.append(SceneryEntry(path=raw_path, disabled=True))

    def write(self, path: str | None = None) -> None:
        out_path = path or self.path
        if not out_path:
            return
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write("I\n1000 Version\n\n")
            for entry in self._entries:
                prefix = "SCENERY_PACK_DISABLED " if entry.disabled else "SCENERY_PACK "
                f.write(f"{prefix}{entry.path}\n")

    def entries(self) -> list[SceneryEntry]:
        return self._entries

    def add_entry(self, path: str, position: int | None = None) -> None:
        entry = SceneryEntry(path=path)
        if position is None or position >= len(self._entries):
            self._entries.append(entry)
        else:
            self._entries.insert(position, entry)

    def remove_entry(self, path: str) -> bool:
        for i, e in enumerate(self._entries):
            if e.path == path:
                self._entries.pop(i)
                return True
        return False

    def find_by_path(self, path: str) -> int | None:
        for i, e in enumerate(self._entries):
            if e.path == path:
                return i
        return None
