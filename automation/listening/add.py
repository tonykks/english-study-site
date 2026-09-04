from __future__ import annotations

import argparse
import logging
import sys

from automation.listening.pipeline import run_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Add a YouTube video as Listening content (Level 1/2/3)."
    )
    parser.add_argument("--url", help="YouTube URL or 11-char video_id")
    parser.add_argument("--level", type=int, choices=[1, 2, 3], required=True)
    parser.add_argument("--dry-run", action="store_true", help="Stage + validate only; no publish")
    parser.add_argument("--fixture", help="Use test fixture JSON name (e.g. sample_segments.json)")
    parser.add_argument("--comparison", action="store_true", help="Write output to automation/.comparison/<video_id>/ without modifying repo")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    if not args.url and not args.fixture:
        parser.error("--url or --fixture is required")

    url = args.url or "fixture://local"
    result = run_pipeline(url, args.level, dry_run=args.dry_run, fixture=args.fixture, comparison=args.comparison)

    print(f"Status: {result.status}")
    print(f"Message: {result.message}")
    if result.video_id:
        print(f"Video ID: {result.video_id}")
    if result.folder:
        print(f"Folder: {result.folder}")
    if result.staging_dir:
        print(f"Staging: {result.staging_dir}")

    if result.status == "BLOCKED":
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
