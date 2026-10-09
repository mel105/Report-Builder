"""Static PNG charts (matplotlib) sized for an A4 portrait text column."""
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .fmt import num  # noqa: E402

# Categorical colours in fixed order; a series keeps its colour in every chart.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
INK, INK_2, MUTED, GRID = "#0b0b0b", "#52514e", "#898781", "#e4e3df"
WIDTH_IN = 6.5   # ~16.5 cm text column
DPI = 200

plt.rcParams.update({
    "font.size": 8.5, "font.family": "DejaVu Sans",
    "axes.edgecolor": MUTED, "axes.labelcolor": INK_2, "axes.linewidth": 0.6,
    "xtick.color": INK_2, "ytick.color": INK_2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 9, "axes.titleweight": "bold", "axes.titlecolor": INK,
    "legend.frameon": False, "figure.facecolor": "white", "savefig.facecolor": "white",
})


def _finish(fig, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    return path


def _grid(ax, axis: str) -> None:
    ax.grid(axis=axis, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(length=0)


def hbar(labels: Sequence[str], values: Sequence[float], path: Path, xlabel: str,
         colors: Optional[Sequence[str]] = None, ref: Optional[Tuple[float, str]] = None,
         decimals: int = 2, legend: Optional[List[Tuple[str, str]]] = None) -> Path:
    """Horizontal bars, first item on top. ref = (value, label) draws a reference line."""
    n = len(labels)
    fig, ax = plt.subplots(figsize=(WIDTH_IN, max(1.6, 0.24 * n + 0.8)))
    pos = range(n)[::-1]
    ax.barh(list(pos), values, height=0.62, color=colors or SERIES[0])
    ax.set_yticks(list(pos), labels)
    ax.set_xlabel(xlabel)
    _grid(ax, "x")
    top = max(values) if values else 1.0
    for p, v in zip(pos, values):
        ax.text(v + top * 0.01, p, num(v, decimals), va="center", ha="left", color=INK, fontsize=7.5)
    ax.set_xlim(0, top * 1.12)
    if ref:
        ax.axvline(ref[0], color=INK_2, linewidth=0.9, linestyle=(0, (4, 3)))
        ax.text(ref[0], n - 0.35, " " + ref[1], color=INK_2, fontsize=7.5, va="bottom", ha="left")
        ax.set_ylim(-0.6, n + 0.2)
    if legend:
        handles = [plt.Rectangle((0, 0), 1, 1, color=c) for _, c in legend]
        ax.legend(handles, [name for name, _ in legend], loc="lower left",
                  bbox_to_anchor=(0, 1.0), ncol=len(legend), fontsize=7.5)
    return _finish(fig, path)


def panels(items: Sequence[Tuple[str, Sequence[str], Sequence[float]]], path: Path,
           ylabel: str, decimals: int = 2, cols: int = 2) -> Path:
    """Small multiples of vertical bars sharing one y scale. items = (title, labels, values)."""
    rows = (len(items) + cols - 1) // cols
    fig, axes = plt.subplots(rows, cols, figsize=(WIDTH_IN, 2.3 * rows), sharey=True, squeeze=False)
    flat = [ax for row in axes for ax in row]
    for ax, (title, labels, values) in zip(flat, items):
        ax.bar(range(len(labels)), values, width=0.62, color=SERIES[0])
        ax.set_xticks(range(len(labels)), labels, rotation=0 if len(labels) <= 4 else 30,
                      ha="center" if len(labels) <= 4 else "right")
        ax.set_title(title, loc="left")
        _grid(ax, "y")
        for i, v in enumerate(values):
            ax.text(i, v, num(v, decimals), ha="center", va="bottom", color=INK, fontsize=7)
    for ax in flat[len(items):]:
        ax.set_visible(False)
    for row in axes:
        row[0].set_ylabel(ylabel)
    fig.tight_layout()
    return _finish(fig, path)


def category_bars(labels: Sequence[str], values: Sequence[float], groups: Sequence[str],
                  path: Path, ylabel: str, xlabel: str) -> Path:
    """Many thin bars (e.g. one per run) coloured by a 2-4 value category, with a legend."""
    order = list(dict.fromkeys(groups))
    colour = {g: SERIES[i] for i, g in enumerate(order)}
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 2.9))
    ax.bar(range(len(values)), values, width=0.7, color=[colour[g] for g in groups])
    step = max(1, len(labels) // 12)
    ax.set_xticks(range(0, len(labels), step), [labels[i] for i in range(0, len(labels), step)],
                  rotation=30, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_xlabel(xlabel)
    _grid(ax, "y")
    handles = [plt.Rectangle((0, 0), 1, 1, color=colour[g]) for g in order]
    ax.legend(handles, order, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=len(order), fontsize=8)
    return _finish(fig, path)


def along_track(km: Sequence[float], values: Sequence[float], path: Path, ylabel: str) -> Path:
    """Stems at track positions (hotspots along the line)."""
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 2.6))
    ax.vlines(km, 0, values, color=SERIES[0], linewidth=1.6)
    ax.scatter(km, values, s=14, color=SERIES[0], zorder=3, edgecolor="white", linewidth=0.6)
    ax.set_xlabel("Staničenie [km]")
    ax.set_ylabel(ylabel)
    ax.set_ylim(0, max(values) * 1.1 if values else 1)
    _grid(ax, "y")
    return _finish(fig, path)


def grouped_bars(labels: Sequence[str], series: Sequence[Tuple[str, Sequence[float]]],
                 path: Path, ylabel: str, xlabel: str = "", decimals: int = 2) -> Path:
    """Vertical bars, 2-3 series side by side per label (e.g. before / after per run)."""
    n, k = len(labels), len(series)
    fig, ax = plt.subplots(figsize=(WIDTH_IN, 2.9))
    width = 0.8 / k
    for j, (name, values) in enumerate(series):
        xs = [i - 0.4 + width * (j + 0.5) for i in range(n)]
        ax.bar(xs, values, width=width * 0.9, color=SERIES[j], label=name)
        if n <= 12:
            for x, v in zip(xs, values):
                ax.text(x, v, num(v, decimals), ha="center", va="bottom", color=INK, fontsize=6.5)
    step = max(1, n // 12)
    ax.set_xticks(range(0, n, step), [labels[i] for i in range(0, n, step)],
                  rotation=0 if n <= 8 else 30, ha="center" if n <= 8 else "right")
    ax.set_ylabel(ylabel)
    if xlabel:
        ax.set_xlabel(xlabel)
    _grid(ax, "y")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=k, fontsize=8)
    return _finish(fig, path)
