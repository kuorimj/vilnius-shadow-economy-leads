# DECISIONS

## Architecture

The system has to run with one command on a clean machine, from a public repository, and handles a small data volume (a few thousand listings, under 100,000 companies per month). Every tool choice was filtered against those two constraints.

| Area | Chosen | Considered and rejected | Why |
|---|---|---|---|
| Where it runs | Local Docker Compose: pipeline and Postgres | AWS (free trial), Databricks Free Edition | Reviewers can't run a cloud deployment in my account. Databricks Free Edition is serverless only, with restricted outbound internet. The data fits on a laptop. |
| Orchestration | Plain Python pipeline with a `--month` flag and idempotent stages | Airflow in Docker | Several extra containers and about 4 GB of RAM for a monthly five-step job. |
| Storage | Postgres 18 | SQL Server (my background) | SQL Server images are x86-only and need Microsoft's ODBC driver. Postgres has `pg_trgm` for fuzzy name matching. |
| Infrastructure as code | `docker-compose.yml` and a Dockerfile | Terraform | No cloud resources to provision. Secrets live in a gitignored `.env`. |
| Google collection | Oxylabs Web API, behind one `fetch_google_local(query)` function | Google Places API; my own scraper | The Places API limits how long most content may be cached, which conflicts with monthly history. Direct scraping conflicts with Google's terms, which the brief asks to respect. |
| Declared data | Downloaded directly from Registrų centras (company register, financial statements) and Sodra (monthly employer data) | Third-party company databases (e.g. Rekvizitai) | Official and free. Aggregators republish the same data and would need scraping. |
| Analyst output | CSV export plus the `mart.leads` table, queryable with SQL | Streamlit UI | Cut for now due to time: matching and scoring quality mattered more than an interface. A UI on top of `mart.leads` is the natural next step. |
| Raw data for replay | Google pages gzipped unchanged; Vilnius-only extracts of the official files (original lines); 34 MB in Git | Parquet; Git LFS | Gzip keeps the source bytes identical, and live and replay read the same format. LFS would force reviewers to install extra tooling. |

**Production path:** the same stages as Airflow tasks, one DAG run per month, defined in Terraform. On GCP: Cloud Composer, raw pages in Cloud Storage, tables in BigQuery, the API key in Secret Manager. On AWS: MWAA, S3, RDS or Athena, Secrets Manager.

## Google data collection

- One page-1 query per category (cafés/restaurants, hair/beauty, car repair) and Vilnius neighbourhood (the city's 21 official *seniūnijos*): 63 pages. City-wide queries rank prominent central places first; neighbourhood queries reach local businesses.
- Requests fault intermittently (34% of attempts succeeded): up to 5 attempts with backoff, every attempt logged, saved pages skipped on re-runs.
- Raw pages are kept unchanged, duplicates included. Staging deduplicates by Google's place ID (CID) and keeps places inside Vilnius by coordinates.
- The parser handles both card layouts Google serves and is tested on real pages of each.

**November 2026 snapshot:** 55 of 63 pages (87%), 855 listings, 736 unique places in Vilnius. The 8 failed pages are reported per run and in `staging.google_coverage`. Two retried pages each added 15 to 17 places no other query found, so the remaining gaps are real blind spots.

## Declared data

- Register and Sodra are joined by company code. Only companies with a Vilnius city address are loaded (85,893), so a Vilnius business registered elsewhere is missed.
- Sodra adds each company's declared activity code (used for matching and staffing baselines). It is two months behind: September 2026.
- **Revenue** comes from profit (loss) statements via the open data API (get.data.gov.lt), fetched only for the 84 confirmed companies and saved for replay. 78 have statements, up to 10 years back. The latest is 2025 for 49 and 2024 for 29, so revenue is one to two years old.

## Matching

Google's local results never say which company runs a place, and brand names rarely equal legal names ("Public" is run by UAB "Asia Pacific"). Matching is therefore deliberately conservative.

- **Rule:** the place's *distinctive* name (without legal forms, generic words like *autoservisas, kirpykla, kavinė*, and neighbourhood names) is at least 80% similar to one company's, **and** a second signal confirms it: the company's declared activity fits the category, or it is registered at the same street address.
- **Address only confirms.** About 94 companies share a typical place's address (business centres, accountants), and 56% of confirmed companies are registered elsewhere, so an address neither decides nor rules out a match.
- **Outcomes:** 87 confirmed, 67 possible, 6 ambiguous, 576 unmatched. Only confirmed matches can become leads; "unmatched" means "can't assess", not "suspicious".
- **Rejected:** address-only matching; looser name thresholds (generic names like "Autoservisas" matched several unrelated companies); collecting websites (none in local results, and many small businesses have none).

## Scoring

- The unit is a **company**, since one company can run several places (their reviews are summed).
- **Staff leads** (undeclared work): reviews at least the **median for the category**; declared employees no more than the **median Vilnius company with the same activity** (7 food service, 2 hair and beauty, 4 car repair); and **reviews per employee at least 3x the category median**. Without the staffing condition, big, properly staffed tourist restaurants (44 employees) ranked near the top; without the busyness condition, every quiet one-person business would.
- **Sales leads** (undeclared sales): busy, and the declared figures **contradict each other**: revenue at most half the previous year's, or below the estimated wage bill (insured x average wage x 12). Sodra hides the average wage for companies with 1 to 3 insured, so the wage check covers only 60 of the 84 confirmed companies.
- **Rejected:** reviews per euro of revenue as a lead rule. It flagged 10 new companies, mostly Old Town restaurants with 19 to 44 staff and steady revenue: tourists, not hidden sales.
- **Supporting reasons**, shown but never creating a lead alone: low revenue for the reviews; employees fell by half from the 2026 peak; Google lists the business as older than its company; liquidation or bankruptcy. Thresholds live in `config.py`.
- **Caveats** travel with each lead: reviews accumulate over years and include tourists; MB owners may work without being insured; staff or sales may sit in a related company; data lags.
- **Result:** 8 leads from 84 confirmed companies: 7 staff, 1 sales. Revenue backs 3 staff leads and looks normal for 2.

## Data quality

- 16 checks between layers, each a SQL query with an allowed range set from the November baseline: row counts, freshness (pages fetched in the snapshot month, Sodra at most 3 months behind), nulls, and plausibility (confirmed match share 5 to 30%, revenue for 80% of confirmed companies).
- A failed **error** check stops the run before scoring with a non-zero exit, so no lead list is published from broken data and CI fails. **Warnings** are only reported. All results are kept in `mart.quality_checks`.

## History across months

- Tables are keyed by `snapshot_month`, stored as a date (the month's first day, enforced by a `month_start` domain), and a run replaces only its month, so monthly facts accumulate (Sodra already holds nine months). Views give month-to-month changes in reviews and insured employees.
- Companies and places get versioned dimensions (SCD type 2): a change of name, address, status or activity, or disappearing, closes the current row. Versions are rebuilt from all stored months each run, so re-runs and back-fills are idempotent.
- With one Google month, every place has one version; the logic is tested on made-up months.

## Scope and next steps

- **Cut for time:** the analyst UI. For now the results are a CSV file and the `mart.leads` table. Loaders have no tests of their own; CI covers them by running the whole pipeline on every pull request.
- **Next:** a simple analyst UI over `mart.leads` and `staging.google_coverage`; from the December run, score busyness by reviews gained per month rather than lifetime totals; fill the 8 coverage gaps; the register's official list of late filers as a supporting reason; add the address register's coordinates as a distance signal for matching (it helps only companies registered where they operate); integration tests per loader; a monthly schedule.
