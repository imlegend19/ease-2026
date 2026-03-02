"""Generate reviewer-focused robustness artifacts for threshold sensitivity."""

from __future__ import annotations

import argparse

from ease2026.analysis.reviewer_robustness import ReviewerRobustnessGenerator
from ease2026.core.logging import setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate reviewer robustness summary CSV and figures using the "
            "Pareto neighborhood {(15/85),(20/80),(25/75),(30/70)} x q={0.50,0.75}."
        ),
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

    output_paths = ReviewerRobustnessGenerator().run(
        dpi=args.dpi,
        save_svg=not args.no_svg,
    )
    print("Generated reviewer robustness artifacts:")
    for key, path in sorted(output_paths.items()):
        print(f"- {key}: {path}")


if __name__ == "__main__":
    main()
