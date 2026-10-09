"""Number formatting for report text and tables."""
import re
from typing import Any, Optional

# Slovak reports use a decimal comma. Set to False for a decimal point.
DECIMAL_COMMA = True
THOUSANDS_SEP = " "  # non-breaking space


def num(value: Any, decimals: int = 0, sign: bool = False) -> str:
    """Format a number; None / NaN -> '-'. Non-numbers are returned as text."""
    if value is None:
        return "-"
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return str(value)
    if value != value:  # NaN
        return "-"
    text = f"{value:+,.{decimals}f}" if sign else f"{value:,.{decimals}f}"
    text = text.replace(",", "\x00")
    if DECIMAL_COMMA:
        text = text.replace(".", ",")
    return text.replace("\x00", THOUSANDS_SEP)


def pct(fraction: Optional[float], decimals: int = 2) -> str:
    """Format a share given as a fraction (0..1) as a percentage number."""
    return "-" if fraction is None else num(100.0 * fraction, decimals)


def to_number(text: Any) -> Optional[float]:
    """Parse '1,273', '+51.3%', '0.3050', '20,624 (100.0%)' -> float, else None.
    Used for TextReport JSON cells, which arrive as preformatted strings."""
    if isinstance(text, bool):
        return None
    if isinstance(text, (int, float)):
        return float(text)
    if not isinstance(text, str):
        return None
    token = text.strip().split(" ")[0].rstrip("%").replace(",", "")
    try:
        return float(token)
    except ValueError:
        return None


_NUM_TOKEN = re.compile(r"(?<![\w.,])[-+]?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+)(?![\w]*\.\d)")


def loc(value: Any) -> str:
    """Localise numbers inside preformatted source text: '10,337,673' -> '10 337 673',
    '0.3050 km/h' -> '0,3050 km/h', '+51.3%' -> '+51,3 %'. Integers without a
    thousands separator (run IDs, counts) and everything non-numeric stay as they are."""
    if value is None:
        return "-"
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, int):
        return num(value)
    if isinstance(value, float):
        return num(value, 4).rstrip("0").rstrip(",.") if value != int(value) else num(value)
    text = str(value)
    if not DECIMAL_COMMA:
        return text
    if text.startswith(("[", "(")):
        text = text.replace(", ", "; ")   # '[0.25, 1.00)' -> '[0,25; 1,00)'

    def swap(m):
        return m.group(0).replace(",", "\x00").replace(".", ",").replace("\x00", THOUSANDS_SEP)

    text = _NUM_TOKEN.sub(swap, text)
    return re.sub(r"(\d)%", "\\1\u00a0%", text)
