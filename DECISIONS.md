## Architecture

The system has to run with one command on a clean machine, from a public repository, and handles a small data volume (a few thousand listings and legal entities per month). Every tool choice below was filtered against those two constraints.

| Area | Chosen | Considered and rejected | Why |
|---|---|---|---|
| Where it runs | Local Docker Compose: pipeline, Postgres and analyst UI | AWS (free trial), Databricks Free Edition | Reviewers can't run a cloud deployment in my account. Databricks Free Edition is serverless only, has restricted outbound internet and is for non-commercial use. The data fits on a laptop. |
| Orchestration | Plain Python pipeline with a `--month` flag and idempotent stages | Airflow in Docker | Airflow needs several extra containers and about 4 GB of RAM for a five-step job that runs once a month. |
| Storage | Postgres 18 | SQL Server (my background)| SQL Server images are x86-only and need Microsoft's ODBC driver. Postgres adds `pg_trgm` and `unaccent` for fuzzy matching of Lithuanian names. |
| Infrastructure as code | `docker-compose.yml` and a Dockerfile | Terraform | There are no cloud resources to provision. Secrets live in a gitignored `.env`. |
| Repository | One repository | Separate code and infrastructure repositories | The reviewer clones one thing and runs one command, and the history stays in one place. |
| Google data collection | Oxylabs Web API to start, behind a swappable `fetch_listings(category, area)` interface. May also try collecting Google's local results directly with my own scraper, as a second implementation of the same interface | Google Places API (kept as fallback) | Oxylabs requests fault intermittently, so a direct collector is worth testing. It would be low volume and rate-limited, but direct scraping conflicts with Google's terms, which the brief asks to respect, so it stays an experiment rather than the default. The Places API limits how long most content may be cached, which conflicts with monthly history. |
| Declared activity data | Collected directly from the official sources: data.gov.lt API (get.data.gov.lt), Sodra open company data (atvira.sodra.lt), Registrų centras | Third-party company databases and aggregators | Official, free, regularly updated and available as APIs or downloads, so no scraping and no intermediary is needed. |

**Production path:** the same stages move to managed services, with an orchestrator (Airflow/MWAA or Step Functions), managed Postgres (RDS) and raw snapshots in S3, defined in Terraform.