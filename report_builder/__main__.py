"""Command line: python -m report_builder gui | list | build <profile> --input ..."""
import argparse
import sys
from pathlib import Path

from . import __version__
from .core.build import build_report, scan
from .profiles import load_all


def main() -> int:
    parser = argparse.ArgumentParser(prog="report_builder",
                                     description=f"report_builder {__version__}")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("gui", help="open the window (default when no command is given)")
    p_list = sub.add_parser("list", help="show profiles; with --input also which ones find data")
    p_list.add_argument("--input", type=Path)
    p_build = sub.add_parser("build", help="build one report")
    p_build.add_argument("profile")
    p_build.add_argument("--input", type=Path, required=True,
                         help="file or folder with the profile's source data")
    p_build.add_argument("--out", type=Path, default=Path("report_out"))
    p_build.add_argument("--template", type=Path, help="DOCX template (title page, styles)")
    p_build.add_argument("--author", default="")
    p_build.add_argument("--status", default="Draft")
    args = parser.parse_args()

    if args.command in (None, "gui"):
        from .gui import run
        return run()

    profiles = load_all()
    if args.command == "list":
        found = scan(profiles, args.input)
        for name, prof in profiles.items():
            state = ("  [data found]" if found[name] else "  [no data]") if args.input else ""
            print(f"{name:<20}{prof.DESCRIPTION}{state}")
        return 0

    prof = profiles.get(args.profile)
    if prof is None:
        print(f"Unknown profile '{args.profile}'. Available: {', '.join(profiles)}", file=sys.stderr)
        return 2
    try:
        result = build_report(prof, args.input, args.out, args.template, args.author, args.status)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    print(f"Report : {result.report}  ({result.tables} tables, {result.figures} figures)")
    print(f"Tables : {result.out_dir / 'tables'}  (CSV)")
    print(f"Figures: {result.out_dir / 'figures'}  (PNG)")
    for w in result.warnings:
        print(f"WARNING: {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
