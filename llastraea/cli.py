"""Command line entry point for llastraea."""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import __version__
from .core import judge_directory, judge_pypi_package
from .render import is_tty, render_markdown, render_text


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llastraea",
        description="Judge whether an open-source project is trustworthy.",
    )
    parser.add_argument("target", nargs="?", default=".",
                        help="Local project directory, or a PyPI package name")
    parser.add_argument("--format", choices=["text", "json", "markdown"],
                        default="text", help="Output format (default: text)")
    parser.add_argument("--output", metavar="FILE",
                        help="Write output to FILE instead of stdout")
    parser.add_argument("--no-color", action="store_true",
                        help="Disable ANSI colours even on a TTY")
    parser.add_argument("--check-latest", action="store_true",
                        help="Reserved for future PyPI version checks; currently a no-op note")
    parser.add_argument("--version", action="version",
                        version=f"llastraea {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    use_colour = is_tty(sys.stdout) and not args.no_color
    try:
        if os.path.isdir(args.target):
            verdict = judge_directory(args.target)
        elif os.path.exists(args.target):
            print(f"error: {args.target!r} is a file, pass a project directory",
                  file=sys.stderr)
            return 2
        else:
            verdict = judge_pypi_package(args.target)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        output = json.dumps(verdict.to_dict(), indent=2)
    elif args.format == "markdown":
        output = render_markdown(verdict)
    else:
        output = render_text(verdict, use_colour)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(output + "\n")
    else:
        print(output)
    return 0 if verdict.overall != "Guilty" else 1


if __name__ == "__main__":
    raise SystemExit(main())
