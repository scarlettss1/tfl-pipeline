# TfL Tube Line Status Pipeline

A data pipeline that polls Transport for London's Unified API for live Tube line status and builds up a historical record over time — data TfL itself doesn't publish, since the API only ever returns the *current* status.

## Why this project exists

This is a project built to demonstrate a real, defensible batch ETL pattern: raw ingestion, a transformation layer, and a clean, queryable dataset - the same shape used in production data pipelines, at a scale that's realistic to build and explain end to end. Every design decision below was made deliberately, based on inspecting the actual API response.

## How it works

1. **Extract** — `fetch_status.py` calls `https://api.tfl.gov.uk/Line/Mode/tube/Status` and stores the full, unmodified JSON response as a new row in `raw_snapshots`.
2. **Store raw** — every poll is appended, never overwritten, building a permanent, untouched historical record.
3. **Transform** — `transform_status.py` reads any snapshots not yet processed, extracts the fields relevant to line status, and writes one row per line per snapshot into `clean_line_status`.
4. **Query** — `clean_line_status` is a flat, indexable table suited to answering real questions (e.g. "how often is the Central Line delayed?") that would be difficult to ask directly against nested JSON.

```
TfL API → fetch_status.py → raw_snapshots (JSONB) → transform_status.py → clean_line_status
```

## Key design decisions

**Raw and clean tables are kept separate.** `raw_snapshots` stores each API response exactly as received, in a `JSONB` column, and is never modified after insert. `clean_line_status` is derived entirely from it. This matters because the transform logic is the part most likely to have bugs or need revisiting - if a mistake is found in how fields are being extracted, the clean table can be dropped and rebuilt from `raw_snapshots` without having lost any original data. The raw table is the permanent source of truth, and the clean table is disposable and regenerable.

**`clean_line_status` uses a composite primary key of `(snapshot_id, line_id)`.** A given line's `line_id` (e.g. `"central"`) is consistent across every snapshot — it repeats every single time the pipeline runs, so it can't uniquely identify a row on its own. `snapshot_id` alone isn't enough either, since one snapshot produces ~11 rows (one per line). Only the *combination* of which line and which specific snapshot it came from is guaranteed unique, which is what a composite key enforces. `snapshot_id` is also a foreign key referencing `raw_snapshots(id)`, so every clean row can be traced back to the exact raw API response it was derived from.

**Not every field from the API response was kept.** The raw JSON includes a lot of information alongside the useful fields. Some examples of deliberate omissions, based on inspecting real responses are:
- `modeName` was dropped — every row in this dataset is `"tube"`, so it can never help distinguish or filter anything.
- `created` and `modified` inside `lineStatuses` were dropped — both were consistently placeholder values (`"0001-01-01T00:00:00"`), not real timestamps.
- `disruption.description` was dropped as redundant with `lineStatuses[0].reason`, which contains the same text.
- `validityPeriods` (`fromDate`/`toDate`/`isNow`) was deliberately excluded from the clean table — it's a list nested inside each line status, and doesn't fit cleanly as flat columns without further design work.

**Re-running the transform script never creates duplicates.** `transform_status.py` only processes snapshots whose `id` doesn't already appear in `clean_line_status`, so it's safe to run repeatedly without needing to track state separately or manually avoid re-processing.

**All credentials are kept out of source code.** `DB_PASSWORD` and `TFL_API_KEY` are loaded from a local `.env` file via `python-dotenv`, and `.env` is excluded from version control via `.gitignore`. This applies even to the TfL key, which isn't strictly an access-control secret (the API is open data) but is still tied to this project's personal rate-limit allowance. Treating all credentials the same way avoids ever accidentally being inconsistent about it.

## Tech stack

- **Language:** Python 3.14
- **Database:** PostgreSQL, run via Docker (`test-postgres` container)
- **Libraries:** `psycopg2` (database access), `requests` (API calls), `python-dotenv` (secrets management)
- **API:** [TfL Unified API](https://api.tfl.gov.uk) — Line Status endpoint

## Running it locally

**Prerequisites:**
- Docker Desktop, with a running Postgres container (`docker run --name test-postgres -e POSTGRES_PASSWORD=<password> -p 5432:5432 -d postgres`)
- Python 3.14+ and the packages in `requirements.txt` (`pip install -r requirements.txt`)
- A `.env` file in the project root containing:
  ```
  DB_PASSWORD=<your postgres password>
  TFL_API_KEY=<your TfL API key>
  ```
  (Register for a free key at [api-portal.tfl.gov.uk](https://api-portal.tfl.gov.uk) — not required to use the API, but raises the rate limit from 50 to 500+ requests.)

**Setup and run, in order:**
```bash
python3 create_db.py        # creates the tfl_pipeline database (run once)
python3 create_tables.py    # creates raw_snapshots and clean_line_status (safe to re-run)
python3 fetch_status.py     # polls the TfL API, stores one new raw snapshot
python3 transform_status.py # transforms any new raw snapshots into clean rows
```

`fetch_status.py` and `transform_status.py` are both designed to be run repeatedly — each call to `fetch_status.py` adds one new snapshot, and `transform_status.py` picks up whatever hasn't been processed yet.

## What's next

This project is a work in progress. Planned next steps:
- Basic automated tests around the transform logic
- Scheduling `fetch_status.py` to run automatically (e.g. every 10–15 minutes) to build up meaningful historical data over time
- Containerising the whole pipeline with Docker so it can be run without any local setup
- Revisiting `validityPeriods` if a concrete need for that data emerges