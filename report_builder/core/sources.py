"""Input side: locating files and loading machine-readable sources."""
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .fmt import to_number

_TS = re.compile(r"(\d{8}_\d{6})")


@dataclass
class Source:
    """One input file, listed in the 'sources' table of every report."""
    path: Path
    generated: str = ""
    note: str = ""


@dataclass
class TextReportData:
    """Content of a TextReport JSON sidecar (LIB/report_writer.py)."""
    title: str
    campaign: Optional[str]
    generated: str
    tables: Dict[str, dict] = field(default_factory=dict)        # heading -> {columns, rows}
    values: Dict[str, Dict[str, str]] = field(default_factory=dict)  # heading -> {key: value}
    notes: Dict[str, List[str]] = field(default_factory=dict)     # heading -> lines without 'key: value'

    def table(self, heading: str) -> dict:
        return self.tables[_norm(heading)]

    def value(self, heading: str, key: str) -> Optional[str]:
        return self.values.get(_norm(heading), {}).get(key)

    def number(self, heading: str, key: str) -> Optional[float]:
        return to_number(self.value(heading, key))


def _norm(heading: str) -> str:
    # Modules pass headings in mixed case; the .txt upper-cases them.
    return heading.strip().upper()


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_textreport(path: Path) -> TextReportData:
    raw = load_json(path)
    data = TextReportData(raw.get("title", ""), raw.get("campaign"), raw.get("generated", ""))
    for block in raw.get("blocks", []):
        key = _norm(block["heading"])
        if block["type"] == "table":
            data.tables[key] = {"columns": block["columns"], "rows": block["rows"]}
            continue
        values, notes = {}, []
        for line in block.get("lines", []):
            name, sep, rest = line.partition(":")
            if sep and name.strip() and len(name) <= 60:
                values[name.strip()] = rest.strip()
            elif line.strip():
                notes.append(line.strip())
        data.values[key] = values
        data.notes[key] = notes
    return data


def newest(directory: Path, pattern: str) -> Optional[Path]:
    """Newest file matching the glob: by YYYYMMDD_HHMMSS in the name, else by mtime."""
    files = list(Path(directory).glob(pattern))
    if not files:
        return None

    def key(p: Path):
        m = _TS.search(p.name)
        if m:
            try:
                return datetime.strptime(m.group(1), "%Y%m%d_%H%M%S")
            except ValueError:
                pass
        return datetime.fromtimestamp(p.stat().st_mtime)

    return max(files, key=key)


def load_plain_kv(path: Path) -> Dict[str, str]:
    """'Key: value' lines of a plain-text report that has no JSON sidecar yet.
    First occurrence of a key wins. Interim reader - prefer load_textreport()."""
    values: Dict[str, str] = {}
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        name, sep, rest = line.partition(":")
        if sep and name.strip() and rest.strip():
            values.setdefault(name.strip(), rest.strip())
    return values
