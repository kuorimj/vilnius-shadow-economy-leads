import argparse
import os
import sys

import psycopg

from shadow.config import AREAS, CATEGORIES
from shadow.extract.google_collect import collect, load_attempts, load_raw
from shadow.load.coverage import load_coverage
from shadow.load.google import load_google


def parse_args():
    parser = argparse.ArgumentParser(description="Shadow economy lead pipeline")
    parser.add_argument("--month", required=True, help="Snapshot month, format YYYY-MM")
    parser.add_argument("--mode", choices=["live", "replay"], default="replay")
    parser.add_argument("--categories", nargs="+", choices=list(CATEGORIES), default=list(CATEGORIES))
    parser.add_argument("--areas", nargs="+", choices=list(AREAS), default=list(AREAS))
    return parser.parse_args()


def main():
    args = parse_args()

    if args.mode == "live":
        summary = collect(args.month, args.categories, args.areas)
        print(
            f"Collected {summary['collected']}, already had {summary['already_had']}, "
            f"failed {len(summary['failed'])}"
        )

    records = load_raw(args.month)
    attempts = load_attempts(args.month)
    expected_pages = len(CATEGORIES) * len(AREAS)

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        loaded = load_google(conn, args.month, records)
        missing = load_coverage(conn, args.month, records, attempts)

    print(f"Coverage: {expected_pages - len(missing)} of {expected_pages} pages collected")
    for page in missing:
        print(f"  missing: {page['category']} / {page['area']} ({page['attempts']} attempts)")

    print(f"Loaded {loaded['raw_rows']} listings into raw.google_listings")
    print(f"Built staging.google_places: {loaded['places']} unique places in Vilnius")
    print(f"  excluded, outside Vilnius: {loaded['outside_vilnius']}")
    print(f"  excluded, no location on the page: {loaded['missing_location']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())