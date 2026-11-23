# Shadow economy leads: Vilnius

[![CI](https://github.com/kuorimj/vilnius-shadow-economy-leads/actions/workflows/ci.yml/badge.svg)](https://github.com/kuorimj/vilnius-shadow-economy-leads/actions/workflows/ci.yml)

A monthly pipeline that finds businesses which look busy on Google but declare little activity to the state. It compares Google local results (reviews, rating, location) with the company register, Sodra's monthly insured-employee counts and companies' annual revenue, and produces a ranked list of companies worth a closer look, each with the reasons behind it.

Covered: cafés and restaurants, hair and beauty salons, and car repair shops, across Vilnius' 21 neighbourhoods.

**November 2026 snapshot:** 736 Google places, 87 confidently linked to a company, **8 leads** (7 staff, 1 sales). See [`data/output/leads_2026-11.csv`](data/output/leads_2026-11.csv).

A lead is a reason to look closer, not evidence of wrongdoing. Every lead carries caveats, and [DECISIONS.md](DECISIONS.md) explains the choices and limitations behind it.

## Run it

Requires Docker. No API keys needed: the repository includes the November 2026 raw data.

```
docker compose up --build
```

This starts Postgres, runs the pipeline in replay mode on the committed snapshot, and writes:

- the lead list to `data/output/leads_2026-11.csv`
- all tables to the database (see [Data model](#data-model))

The run ends with a summary: coverage, places, companies, match outcomes, data quality checks and the ranked leads. If a blocking quality check fails, the run stops before scoring and exits with an error.

To query the results while the database is running:

```
docker compose exec db psql -U leads -d leads -c "SELECT rank, places, explanation FROM mart.leads ORDER BY rank"
```

### Live mode

Live mode collects fresh Google pages, downloads the latest register and Sodra files, and fetches revenue for the confirmed companies. It needs an Oxylabs Web API key:

1. Copy `.env.example` to `.env` and set `OXYLABS_WEB_API_KEY`.
2. Run:

```
docker compose run --rm pipeline python -m shadow.run --month 2026-12 --mode live
```

The Oxylabs Google Maps endpoint fails intermittently, so a full run can take a few hours. Each request is retried up to 5 times, every attempt is logged, and already-saved pages are skipped, so a run can be stopped and resumed at any time. `--categories` and `--areas` limit a run for testing, e.g. `--categories cafe_restaurant --areas seskine`.

To prepare a month for committing (compress pages, write Vilnius-only extracts of the declared data):

```
docker compose run --rm pipeline python -m shadow.snapshot --month 2026-12
```

### Tests and checks

```
python -m venv .venv
# activate the virtual environment, then:
pip install -r requirements-dev.txt
python -m pytest
ruff check src tests
mypy
```

`requirements.txt` holds only what the pipeline needs to run (it is what the Docker image installs); `requirements-dev.txt` adds pytest, ruff and mypy.

Parser tests run against real Google pages saved in `tests/fixtures/`, including both page layouts Google serves.

## How it works

```
Google local results ──► raw pages (gzipped, unchanged) ──► parse ──► raw.google_listings
  (Oxylabs Web API)                                                       │ deduplicate by Google place ID,
                                                                          ▼ keep places inside Vilnius
                                                               staging.google_places
                                                                          │
Company register ──┐                                                      ▼ match by distinctive name,
                   ├──► staging.companies ─────────────────────► staging.place_matches
Sodra monthly ─────┘    staging.company_monthly                           │ confirmed matches only
                                                                          ▼
                                                                    mart.leads ──► CSV
```

1. **Collect:** one page-1 query per category and neighbourhood (63 pages). Raw responses are saved unchanged with their query and fetch time.
2. **Parse and load:** listings are parsed deterministically from the HTML (name, rating, review count, category, address, coordinates, Google place ID, years in business).
3. **Declared data:** Vilnius companies from the register, joined with Sodra's monthly insured counts by company code. After matching, revenue from the financial statements is fetched for confirmed companies.
4. **Match:** each place is linked to a company only when its distinctive name matches and a second signal confirms it (declared activity fits the category, or the same street address). Outcomes: confirmed, possible, ambiguous, unmatched. Only confirmed matches can become leads.
5. **Score:** two kinds of lead. A **staff** lead is busy for its category, lightly staffed for its activity, and has at least 3x the category median of reviews per employee. A **sales** lead is busy, but its declared revenue halved from the previous year or is below its estimated wage bill.

## Output

`data/output/leads_<month>.csv`, one row per company:

| Column | Meaning |
|---|---|
| `rank` | Staff leads first, by `times_category_median`, then sales leads |
| `lead_type` | `staff` (undeclared work) or `sales` (undeclared sales) |
| `company_code`, `company_name`, `legal_form` | From the company register |
| `places` | The company's Google places |
| `reviews` | Google reviews across those places |
| `insured` | Insured employees in the latest Sodra month |
| `typical_insured` | Median for Vilnius companies with the same declared activity |
| `revenue`, `revenue_year` | Latest annual sales revenue from the financial statements, scaled to 12 months |
| `times_category_median` | Reviews per employee, relative to the category median (staff leads only) |
| `supporting_reasons` | Extra signals, e.g. employees falling during the year, revenue below the wage bill |
| `caveats` | Reasons a lead may be innocent, e.g. small partnership owners not being employees |
| `explanation` | The lead in one sentence |

## Data model

| Schema | Table | Contents |
|---|---|---|
| `raw` | `google_listings` | Every listing from every page, duplicates included, with its source file |
| `staging` | `google_places` | One row per place per month, inside Vilnius |
| `staging` | `google_coverage` | All 63 expected pages: collected or not, attempts, listings |
| `staging` | `companies` | Vilnius companies with their latest declared activity |
| `staging` | `company_monthly` | Monthly insured counts, wages and contributions |
| `staging` | `company_revenue` | Yearly sales revenue per confirmed company, full history |
| `staging` | `place_matches` | Match outcome and evidence for every place |
| `mart` | `leads` | The lead list |
| `mart` | `quality_checks` | Result of every data quality check, per month |
| `mart` | `company_versions`, `place_versions` | Every version of each company and place across months (SCD type 2) |
| `mart` | `place_review_changes`, `company_insured_changes` | Views: month-to-month change in reviews and insured employees |

Every table carries `snapshot_month`, a date holding the month's first day (`2026-11-01`), and each run replaces its month in one transaction, so re-runs are idempotent and monthly snapshots accumulate. The version tables are rebuilt from all stored months on every run.

## Limitations: where it can be wrong

A lead is a reason to look closer. These are the ways the list can be wrong, with examples from the November 2026 run.

### Wrong or missing matches

- **Missed links are the main loss.** Brand names rarely equal legal names ("Public" is run by UAB "Asia Pacific"), so only 87 of 736 places are confirmed. 67 more have one plausible company but no second signal, and 6 have several. They are kept in `staging.place_matches` for review, but never scored. Unmatched places say nothing about the business.
- **A confirmed match can still be the wrong company** if two similarly named companies in the same activity exist and only one has a Vilnius address. The rule needs a second signal (declared activity or the same street address), which makes this rare, not impossible.
- **Companies registered outside Vilnius are not loaded**, so a Vilnius café run by a Kaunas-registered company can't be matched.
- **One company, several places:** reviews are summed per company (three confirmed companies run two places each). If a name match wrongly merges two businesses, the review count is inflated.

### False positives: busy and lightly staffed, but honest

- **People who work without being employees.** Small partnership (MB) owners can work in their business without being insured employees: 3 of the 7 staff leads are MBs (Mimino, Barzdakas, Carmann). In hair and beauty, stylists often rent a chair and pay tax under their own individual activity, so a busy salon can legally employ almost nobody. Barzdakas (insured employees fell from 7 to 0) and Kirpimo Meistrai (1 employee) both fit that pattern as well as the suspicious one.
- **Staff or sales in another company.** A sister company may employ the staff or book the revenue. A sharp revenue drop, like DARMELITA's, can mean the business moved to a new company.
- **Lifetime reviews.** Review counts accumulate over years and include tourists, so an old, popular place with a small current team looks busier than it is. Month-to-month review growth (from the December run) fixes this.
- **Stale declarations.** Sodra is two months behind, and revenue is from 2024 or 2025 statements. The wage check can't be applied to companies with 1 to 3 insured, because Sodra hides their average wage.

### Coverage

- Only the first page (20 places) of each category and neighbourhood query is collected, and 8 of 63 pages failed. A business that isn't on the list was not assessed; it was not found quiet.

How the design limits the damage: only confirmed matches are scored, a lead needs to be busy **and** under-declared relative to its own category, every lead carries its caveats, and no single signal creates a lead on its own.

## Towards production

### Scalability: from 3 categories in Vilnius to every business in Lithuania

- **Declared data is already national.** The register and Sodra files cover the whole country, so loading every municipality instead of Vilnius only is a filter change. In BigQuery, tables would be partitioned by `snapshot_month` and clustered by company code.
- **Google collection is the bottleneck.** Category times neighbourhood queries don't scale to every business type in 60 municipalities. Production would discover places once with a geographic grid of queries, store each place by its Google ID, and refresh known places on a schedule instead of rediscovering them every month. Collection runs as parallel workers (Airflow dynamic tasks or Cloud Run jobs) with rate limits per provider.
- **Matching** compares each place only with companies in the same municipality and activity group (blocking), so the candidate search stays small as the number of companies grows.

### Accuracy of matching and scoring

- **More match signals:** distance between the place and the company's address (from the address register's coordinates), phone and website from place details, and the company's other places.
- **A review queue for "possible" matches.** The analyst's decisions become labelled data, which turns match precision into a measured number instead of an assumption.
- **Feedback from inspections.** Recording which leads were checked and what was found is the only real way to tune thresholds and measure false positives.
- **Better busyness:** reviews gained per month instead of lifetime totals, and category-specific rules (for example, chair rental in hair salons).

### Data freshness and update mechanisms

Sources change at different rates, so each gets its own schedule:

| Source | Changes | Refresh |
|---|---|---|
| Company register | Daily | Daily download, store only changed rows |
| Sodra | Monthly, two months behind | Monthly, after publication |
| Financial statements | Yearly, filed by mid-year | Monthly check for new statements |
| Google listings | Continuously | Monthly for known places, quarterly discovery of new ones |

Scoring runs monthly on the latest available version of each source, and every lead records the as-of date of each input, so the analyst can see how fresh it is.

### Monitoring, observability and data quality

- The 16 quality checks already stop a run on broken data. In production they would compare each month with the previous ones (for example, match rate within a band of its recent average) instead of fixed thresholds, and alert on failure.
- Per-run metrics (pages collected, request success rate, cost, match rate, number of leads) on a dashboard, logging with levels, and schema checks on each source (Sodra parsing already fails on an unexpected header).

### Cost

- Google requests are the main cost, so refresh frequency is the main lever: review counts change slowly, so known places can be refreshed monthly and new-place discovery run less often.
- Failed Oxylabs requests are not charged, so retries cost time, not money.
- Raw pages are stored gzipped in object storage. BigQuery queries stay cheap with partitioning by month and clustering by company.
- Collection and transformation run as short scheduled jobs, not always-on servers.

## Project layout

```
src/shadow/
  run.py              pipeline entry point (--month, --mode)
  snapshot.py         prepares a month's data for committing
  config.py           categories, neighbourhoods and all thresholds
  quality.py          data quality checks between layers
  history.py          versions of companies and places across months
  extract/            Oxylabs client, collector, Google parser, declared-data reader, revenue API client
  load/               loaders for Google data, coverage, declared data and revenue
  match/              name normalisation and place-to-company matching
  score/              lead scoring and CSV export
sql/init/             schema, run on first database start
data/raw/             Google pages and attempts log, per month
data/declared/        Vilnius extracts of the register and Sodra, and revenue API answers, per month
data/output/          lead lists
tests/                unit tests and real-page fixtures
spikes/               early probes of the Oxylabs endpoint
```

## Data sources

- **Google local results**, collected through the [Oxylabs Web API](https://oxylabs.io/).
- **Register of Legal Entities (JAR)**, Registrų centras open data, CC BY 4.0.
- **Insured persons by employer**, Sodra open data ([atvira.sodra.lt](https://atvira.sodra.lt/)).
- **Financial statements (profit and loss)**, Registrų centras, through the national open data API ([data.gov.lt](https://data.gov.lt/)).

## Development workflow

`main` is protected: no direct pushes, including the owner's. Every change goes through a pull request, and merging is blocked until all three CI checks pass:

- `lint`: ruff (style, import order, likely bugs) and mypy (types).
- `unit-tests`: the pytest suite (parser, matching, revenue, scoring, quality checks, history, snapshot).
- `replay`: `docker compose up` on the committed snapshot, which must pass the data quality checks and reproduce `data/output/leads_2026-11.csv` exactly.