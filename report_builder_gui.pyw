"""Double-click launcher for the Report Builder window (no console on Windows)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from report_builder.gui import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run())
