import argparse
import os
import sys

import psycopg

from shadow.config import AREAS, CATEGORIES
from shadow.extract.declared import download_declared, read_declared
from shadow.extract.google_collect import collect, load_attempts, load_raw
from shadow.extract.revenue import collect_revenue, read_revenue_raw, revenue_rows
from shadow.history import load_history
from shadow.load.coverage import load_coverage
from shadow.load.declared import load_declared
from shadow.load.google import load_google
from shadow.load.revenue import load_revenue
from shadow.match.places import confirmed_company_codes, load_matches
from shadow.months import month_arg, month_start
from shadow.quality import INPUT_CHECKS, OUTPUT_CHECKS, blocking, describe, run_checks
from shadow.score.leads import export_csv, load_leads


def parse_args():
    parser = argparse.ArgumentParser(description="Shadow economy lead pipeline")
    parser.add_argument("--month", required=True, type=month_arg, help="Snapshot month, format YYYY-MM")
    parser.add_argument("--mode", choices=["live", "replay"], default="replay")
    parser.add_argument("--categories", nargs="+", choices=list(CATEGORIES), default=list(CATEGORIES))
    parser.add_argument("--areas", nargs="+", choices=list(AREAS), default=list(AREAS))
    return parser.parse_args()


def main():
    args = parse_args()

    if args.mode == "live":
        summary = collect(args.month, args.categories, args.areas)
        print(
            f"Collected {summary.collected}, already had {summary.already_had}, "
            f"failed {len(summary.failed)}"
        )
        download_declared(args.month)

    records = load_raw(args.month)
    attempts = load_attempts(args.month)
    companies, monthly = read_declared(args.month)
    expected_pages = len(CATEGORIES) * len(AREAS)
    snapshot = month_start(args.month)

    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        loaded = load_google(conn, snapshot, records)
        missing = load_coverage(conn, snapshot, records, attempts)
        declared = load_declared(conn, snapshot, companies, monthly)
        matches = load_matches(conn, snapshot)
        if args.mode == "live":
            fetched = collect_revenue(args.month, confirmed_company_codes(conn, snapshot))
            print(f"Revenue: fetched {fetched['fetched']} companies, already had {fetched['already_had']}")
        revenue = load_revenue(conn, snapshot, revenue_rows(read_revenue_raw(args.month)))

        quality = run_checks(conn, snapshot, INPUT_CHECKS, reset=True)
        failed = blocking(quality)
        leads, csv_path, history = [], None, None
        if not failed:
            leads = load_leads(conn, snapshot)
            csv_path = export_csv(leads, args.month)
            quality += run_checks(conn, snapshot, OUTPUT_CHECKS)
            history = load_history(conn)

    print(f"Coverage: {expected_pages - len(missing)} of {expected_pages} pages collected")
    for page in missing:
        print(f"  missing: {page['category']} / {page['area']} ({page['attempts']} attempts)")

    print(f"Loaded {loaded['raw_rows']} listings into raw.google_listings")
    print(f"Built staging.google_places: {loaded['places']} unique places in Vilnius")
    print(f"  excluded, outside Vilnius: {loaded['outside_vilnius']}")
    print(f"  excluded, no location on the page: {loaded['missing_location']}")

    print(f"Loaded {declared['companies']} Vilnius companies into staging.companies")
    print(
        f"  {declared['with_sodra']} with Sodra data: {declared['monthly_rows']} monthly rows, "
        f"latest month {declared['latest_month']}"
    )
    print(f"Matched {loaded['places']} places to companies:")
    for status in ("confirmed", "possible", "ambiguous", "unmatched"):
        print(f"  {status}: {matches[status]}")
    print(f"Loaded {revenue['statements']} revenue statements for {revenue['companies']} confirmed companies")

    passed = sum(r["passed"] for r in quality)
    print(f"Quality checks: {passed} of {len(quality)} passed, results in mart.quality_checks")
    for result in quality:
        if not result["passed"]:
            print(f"  {result['severity'].upper()}: {describe(result)}")
    if failed:
        print("Stopped before scoring: fix the failed error checks above. No lead list was written.")
        return 1

    print(
        f"History: {history['company_versions']} versions of {history['companies']} companies, "
        f"{history['place_versions']} versions of {history['places']} places"
    )

    print(f"Leads: {len(leads)} companies, written to mart.leads and {csv_path}")
    for lead in leads:
        if lead["lead_type"] == "staff":
            signal = f"{lead['times_category_median']}x the category median of reviews per employee"
        else:
            signal = lead["explanation"]
        print(f"  {lead['rank']}. [{lead['lead_type']}] {lead['places']} ({lead['company_name']}): {signal}")

    return 0


if __name__ == "__main__":
    sys.exit(main())