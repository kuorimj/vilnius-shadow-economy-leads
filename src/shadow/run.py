import argparse
import sys

from shadow.config import AREAS, CATEGORIES
from shadow.extract.google_collect import collect, load_raw
from shadow.extract.google_local import html_from_response, parse_listings


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
        for query in summary["failed"]:
            print(f"  failed: {query}")

    records = load_raw(args.month)
    listings = [
        listing
        for record in records
        for listing in parse_listings(html_from_response(record["response"]))
    ]
    unique_places = {listing.cid for listing in listings}
    expected_pages = len(CATEGORIES) * len(AREAS)

    print(f"Raw pages: {len(records)} of {expected_pages} expected")
    print(f"Listings parsed: {len(listings)}, unique places: {len(unique_places)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())