"""Generate final paper figures from analysis outputs."""

from __future__ import annotations

import argparse

from ease2026.analysis.figures import FinalFigureGenerator
from ease2026.core.logging import setup_logging
from ease2026.outcomes.definitions import FixerAttributionPolicy


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=("Generate Figure 1-4 for EASE 2026 from final tables and robustness outputs."),
    )
    parser.add_argument(
        "--fixer",
        choices=(
            FixerAttributionPolicy.ASSIGNEE.value,
            FixerAttributionPolicy.COMMIT_AUTHOR.value,
        ),
        default=FixerAttributionPolicy.ASSIGNEE.value,
        help="Fixer attribution variant used for Figure 3 (default: assignee).",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="Image resolution in DPI (default: 300).",
    )
    parser.add_argument(
        "--no-svg",
        action="store_true",
        help="Disable SVG export (PNG is always generated).",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    setup_logging(debug=args.debug)

    output_paths = FinalFigureGenerator().run(
        fixer_for_rq3=args.fixer,
        dpi=args.dpi,
        save_svg=not args.no_svg,
    )
    print("Generated final figures:")
    for key, path in sorted(output_paths.items()):
        print(f"- {key}: {path}")


if __name__ == "__main__":
    main()
