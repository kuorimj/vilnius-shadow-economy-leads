# DECISIONS

## Architecture

The system has to run with one command on a clean machine, from a public repository, and handles a small data volume (a few thousand listings, under 100,000 companies per month). Every tool choice was filtered against those two constraints.

| Area | Chosen | Rejected | Why |
|---|---|---|---|
| Where it runs | Docker Compose: pipeline and Postgres | AWS trial, Databricks Free Edition | Reviewers can't run my cloud account; Databricks Free has restricted internet; the data fits on a laptop. |
| Orchestration | Python script with a `--month` flag, about nine steps in order | Airflow in Docker | About 4 GB of extra containers for one monthly job. Each step replaces its month, so reruns are safe; per-step runs come from Airflow in production. |
| Storage | Postgres 18 | SQL Server (my background) | SQL Server images are x86-only; Postgres has `pg_trgm` for fuzzy matching. |
| Schema changes | SQL init scripts; rebuild with `docker compose down -v` | Alembic, Flyway | Every table rebuilds from the committed raw files in minutes; production would need migrations. |
| Infrastructure | Compose file and Dockerfile | Terraform | No cloud resources; secrets in a gitignored `.env`. |
| Google collection | Oxylabs Web API behind one function | Places API; my own scraper | The Places API limits caching; scraping breaks Google's terms. |
| Declared data | Registrų centras and Sodra open data | Aggregators (e.g. Rekvizitai) | Official and free; aggregators republish it and would need scraping. |
| Analyst output | CSV and `mart.leads` | Streamlit UI | Cut for time: matching and scoring quality came first. |
| Raw data for replay | Gzipped pages and Vilnius extracts in Git (34 MB) | Parquet; Git LFS | Gzip keeps the source bytes identical; LFS needs extra tooling. |

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

Google never says which company runs a place, and brand names rarely equal legal names ("Public" is run by UAB "Asia Pacific"), so matching is deliberately conservative.

- **Rule:** the place's distinctive name (without legal forms, generic words like *kavinė* and neighbourhood names) is at least 80% similar to one company's, **and** the company's declared activity fits the category or it is registered at the same street address.
- **Address only confirms:** many companies share a business-centre address, and 56% of confirmed companies are registered elsewhere.
- **Outcomes:** 87 confirmed, 67 possible, 6 ambiguous, 576 unmatched. Only confirmed matches can become leads; "unmatched" means "can't assess", not "suspicious".
- **Rejected:** address-only matching, looser name thresholds (generic names matched unrelated companies) and collecting websites (rarely available).

## Scoring

- The unit is a **company**; reviews are summed over its places.
- **Staff leads** (undeclared work): reviews at least the category median, insured employees no more than the median Vilnius company with the same activity, and reviews per employee at least 3x the category median. The first two conditions keep out staffed tourist restaurants and quiet one-person businesses.
- **Sales leads** (undeclared sales): busy, and the declared figures contradict each other: revenue at most half of the previous year's, or below the estimated wage bill (insured x average wage x 12). Sodra hides wages for companies with 1 to 3 insured, so this covers 60 of 84 companies.
- **Rejected:** reviews per euro of revenue as a lead rule. It mostly flagged busy Old Town restaurants with steady revenue: tourists, not hidden sales.
- Supporting reasons (e.g. employees halved, liquidation) and caveats (tourist reviews, MB owners, related companies, data lag) travel with each lead. Thresholds live in `config.py`.
- **Result:** 8 leads from 84 confirmed companies: 7 staff, 1 sales.

## Data quality

- 16 checks between layers, each a SQL query with an allowed range set from the November baseline: row counts, freshness (pages fetched in the snapshot month, Sodra at most 3 months behind), nulls, and plausibility (confirmed match share 5 to 30%, revenue for 80% of confirmed companies).
- A failed **error** check stops the run before scoring with a non-zero exit, so no lead list is published from broken data and CI fails. **Warnings** are only reported. All results are kept in `mart.quality_checks`.

## History across months

- Tables are keyed by `snapshot_month`, stored as a date (the month's first day, enforced by a `month_start` domain), and a run replaces only its month, so monthly facts accumulate (Sodra already holds nine months). Views give month-to-month changes in reviews and insured employees.
- Companies and places get versioned dimensions (SCD type 2): a change of name, address, status or activity, or disappearing, closes the current row. Versions are rebuilt from all stored months each run, so re-runs and back-fills are idempotent.
- With one Google month, every place has one version; the logic is tested on made-up months.

## Scope and next steps

- **Cut for time:** the analyst UI. For now the results are a CSV file and the `mart.leads` table. Loaders have no tests of their own; CI covers them by running the whole pipeline on every pull request.
- **Next:** a simple analyst UI over `mart.leads`; from December, busyness as reviews gained per month instead of lifetime totals; fill the 8 coverage gaps; integration tests per loader; logging with levels; stricter type checking (`mypy --strict` flags 55 places); a monthly schedule in Airflow.
