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

The run ends with a summary: coverage, places, companies, match outcomes and the ranked leads.

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

### Tests

```
python -m venv .venv
# activate the virtual environment, then:
pip install -r requirements.txt
python -m pytest
```

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

Every table carries `snapshot_month`, and each run replaces its month in one transaction, so re-runs are idempotent.

## Project layout

```
src/shadow/
  run.py              pipeline entry point (--month, --mode)
  snapshot.py         prepares a month's data for committing
  config.py           categories, neighbourhoods and all thresholds
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

`main` is protected: no direct pushes, including the owner's. Every change goes through a pull request, and merging is blocked until both CI checks pass:

- `unit-tests`: the pytest suite (parser, matching, revenue, scoring, snapshot).
- `replay`: `docker compose up` on the committed snapshot, which must reproduce `data/output/leads_2026-11.csv` exactly.