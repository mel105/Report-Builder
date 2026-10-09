"""Profile registry. One module in this folder = one report type.

A profile module defines:
    NAME, TITLE, SUBTITLE, DESCRIPTION   (str)
    find_inputs(path) -> dict | None     what it needs, located under `path`
    build(inputs, doc) -> list[Source]   fills the DocBuilder, returns its sources
The orchestrator never changes when a profile is added.
"""
import importlib
import pkgutil
from typing import Dict


def load_all() -> Dict[str, object]:
    found = {}
    for info in pkgutil.iter_modules(__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{__name__}.{info.name}")
        found[module.NAME] = module
    return found
