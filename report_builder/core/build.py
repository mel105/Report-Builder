"""One entry point for building a report - shared by the command line and the GUI."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from .document import DocBuilder


@dataclass
class BuildResult:
    report: Path
    out_dir: Path
    tables: int
    figures: int
    warnings: List[str] = field(default_factory=list)


def scan(profiles: Dict[str, object], input_path: Optional[Path]) -> Dict[str, bool]:
    """Which profiles find usable data under input_path."""
    found = {}
    for name, prof in profiles.items():
        try:
            found[name] = bool(input_path) and prof.find_inputs(Path(input_path)) is not None
        except Exception:
            found[name] = False
    return found


def build_report(prof, input_path: Path, out_root: Path, template: Optional[Path] = None,
                 author: str = "", status: str = "Draft") -> BuildResult:
    """Build one report. Raises ValueError with a readable message when it cannot."""
    inputs = prof.find_inputs(Path(input_path))
    if inputs is None:
        raise ValueError(f"Profile '{prof.NAME}' found no usable data in {input_path}")
    if template and not Path(template).exists():
        raise ValueError(f"Template not found: {template}")
    campaign = inputs.get("campaign", "")
    out_dir = Path(out_root) / f"{prof.NAME}_{campaign}"
    doc = DocBuilder(out_dir, Path(template) if template else None, prof.TITLE, prof.SUBTITLE,
                     campaign, author=author, status=status)
    sources = prof.build(inputs, doc)
    doc.heading("Zdroje správy", numbered=False)
    doc.sources(sources)
    report = doc.save(f"report_{prof.NAME}_{campaign}.docx")
    kinds = [kind for _, kind, _ in doc._captions]
    return BuildResult(report, out_dir, kinds.count("Tabuľka"), kinds.count("Obrázok"),
                       list(inputs.get("warnings", [])))
