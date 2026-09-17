# TfL Tube Line Status Pipeline

A data pipeline that polls Transport for London's Unified API for live Tube line status and builds up a historical record over time. TfL's API only ever returns the *current* status, so this data doesn't exist anywhere else.

## Why this project exists

This is a project built to practise a real batch ETL pattern: pulling data from an API, storing it, transforming it, testing it, and scheduling it to run automatically. The same shape used in real production data pipelines, at a scale that's realistic to build. Every design decision below was made deliberately, based on inspecting the actual API response.

## How it works

1. **Extract** - `fetch_status.py` calls `https://api.tfl.gov.uk/Line/Mode/tube/Status` and stores the full, unmodified JSON response as a new row in `raw_snapshots`.
2. **Store raw** - every poll is appended, never overwritten, building a permanent, untouched historical record.
3. **Transform** - `transform_status.py` reads any snapshots not yet processed, extracts the fields relevant to line status (via `transform_logic.py`), and writes one row per line per snapshot into `clean_line_status`.
4. **Schedule** - an Airflow DAG (`dags/tfl_pipeline_dag.py`) runs the extract and transform steps automatically, every 15 minutes, so the dataset builds up unattended over time.
5. **Query** - `clean_line_status` is a flat, indexable table suited to answering real questions (e.g. "how often is the Central Line delayed?") that would be difficult to ask directly against nested JSON.

```
Airflow (every 15 min)
        │
        ▼
TfL API → fetch_status.py → raw_snapshots (JSONB) → transform_status.py → clean_line_status
```

## Key design decisions

**Raw and clean tables are kept separate.** `raw_snapshots` stores each API response exactly as received, in a `JSONB` column, and is never modified after insert. `clean_line_status` is derived entirely from it. This matters because the transform logic is the part most likely to have bugs or need revisiting, if a mistake is found in how fields are being extracted, the clean table can be dropped and rebuilt from `raw_snapshots` without having lost any original data. The raw table is the permanent source of truth, and the clean table is disposable and regenerable.

**`clean_line_status` uses a composite primary key of `(snapshot_id, line_id)`.** A given line's `line_id` (e.g. `"central"`) is consistent across every snapshot, it repeats every single time the pipeline runs, so it can't uniquely identify a row on its own. `snapshot_id` alone isn't enough either, since one snapshot produces ~11 rows (one per line). Only the *combination* of which line and which specific snapshot it came from is guaranteed unique, which is what a composite key enforces. `snapshot_id` is also a foreign key referencing `raw_snapshots(id)`, so every clean row can be traced back to the exact raw API response it was derived from.

**Not every field from the API response was kept.** The raw JSON includes a lot of information alongside the useful fields. Some examples of omissions, based on inspecting real responses are:
- `modeName` was dropped, every row in this dataset is `"tube"`, so it can never help distinguish or filter anything.
- `created` and `modified` inside `lineStatuses` were dropped, both were consistently placeholder values (`"0001-01-01T00:00:00"`), not real timestamps.
- `disruption.description` was dropped as redundant with `lineStatuses[0].reason`, which contains the same text.
- `validityPeriods` (`fromDate`/`toDate`/`isNow`) was excluded from the clean table, it's a list nested inside each line status, and doesn't fit cleanly as flat columns without further design work.

**Re-running the transform script never creates duplicates.** `transform_status.py` only processes snapshots whose `id` doesn't already appear in `clean_line_status`, so it's safe to run repeatedly.

**Field-extraction logic is separated from database logic.** `extract_line_fields()` lives in its own file, `transform_logic.py`, and takes a plain dictionary in and returns a plain dictionary out, no database connection involved. This is what makes it directly testable (see Testing below) without needing a live database for every test run.

**The database host is configurable via an environment variable, not hardcoded.** `fetch_status.py` and `transform_status.py` read `TFL_DB_HOST` (defaulting to `localhost` if unset), rather than hardcoding it. This lets the exact same, unmodified scripts run correctly both manually on a local machine (`localhost`) and inside Airflow's Docker containers (`test-postgres`, the container's network name), without needing two versions of the code. The variable is deliberately named `TFL_DB_HOST` rather than `DB_HOST`, since `DB_HOST` collides with a variable Airflow's own internal startup scripts use, an early version of this used that name and broke Airflow's scheduler as a result.

**All credentials are kept out of source code.** `DB_PASSWORD` and `TFL_API_KEY` are loaded from a local `.env` file via `python-dotenv`, and `.env` is excluded from version control via `.gitignore`. Treating all credentials the same way avoids ever accidentally being inconsistent about it.

## Testing

`extract_line_fields()` (in `transform_logic.py`) has unit tests in `tests/test_transform_logic.py`, covering:
- A line with "Good Service" (no disruption) - confirms `reason` and `category` correctly come back as `None`
- A line with an active disruption - confirms `reason` and `category` are correctly extracted from the nested `disruption` object
- A line missing `lineStatuses` entirely, and a line with an empty `lineStatuses` list - these document the function's current behaviour (it raises `KeyError` or `IndexError` respectively) rather than fixing it, since this case hasn't been observed in real TfL data

Run with `pytest` from the project root.

## Scheduling

The pipeline runs automatically every 15 minutes via an Airflow DAG (`dags/tfl_pipeline_dag.py`), which runs `fetch_status.py` followed by `transform_status.py` in order. This has been tested and confirmed running unattended over multiple real, scheduled intervals, not just manually triggered.

Airflow itself is run via Docker Compose, set up in a separate local folder (not part of this repo, since it's Airflow's own infrastructure rather than project code). The DAG file is kept here, in `dags/`, for visibility and version control; running it for real requires Airflow to be set up separately, with this project's folder mounted into Airflow's containers and `TFL_DB_HOST=test-postgres` set as an environment variable so the containers can reach the database by its Docker network name. Full local Airflow setup instructions are outside the scope of this README, but the DAG definition itself reflects the real, working configuration.

## Tech stack

- **Language:** Python 3.14
- **Database:** PostgreSQL, run via Docker (`test-postgres` container)
- **Orchestration:** Apache Airflow (via Docker Compose), running on a 15 minute schedule
- **Testing:** pytest
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
  (Register for a free key at [api-portal.tfl.gov.uk](https://api-portal.tfl.gov.uk) - not required to use the API, but raises the rate limit from 50 to 500+ requests.)

**Setup and run, in order:**
```bash
python3 create_db.py        # creates the tfl_pipeline database (run once)
python3 create_tables.py    # creates raw_snapshots and clean_line_status (safe to re-run)
python3 fetch_status.py     # polls the TfL API, stores one new raw snapshot
python3 transform_status.py # transforms any new raw snapshots into clean rows
pytest                       # runs the test suite
```

`fetch_status.py` and `transform_status.py` are both designed to be run repeatedly, each call to `fetch_status.py` adds one new snapshot, and `transform_status.py` picks up whatever hasn't been processed yet. See **Scheduling** above for running them automatically via Airflow instead of manually.

## Running it with Docker
 
The pipeline is also packaged as a Docker image, so it can be run without installing Python or any dependencies locally. This still assumes a running Postgres container reachable over the network, it doesn't remove the need for a database, just the need for a local Python setup.
 
**Prerequisites:**
- Docker Desktop
- A running Postgres container (see the `docker run` command in **Running it locally** above), on the same Docker network as this image will use
- A `.env` file, same as above
**Build the image:**
```bash
docker build -t tfl-pipeline .
```
 
**One-time setup** (creates the database and tables, replace `<network-name>` and `<postgres-container-name>` with your actual setup):
```bash
docker run --env-file .env --network <network-name> -e TFL_DB_HOST=<postgres-container-name> tfl-pipeline python3 create_db.py
docker run --env-file .env --network <network-name> -e TFL_DB_HOST=<postgres-container-name> tfl-pipeline python3 create_tables.py
```
`create_db.py` is not safe to re-run (it will error with `DuplicateDatabase` if run twice), which is expected, this is a one-time step. `create_tables.py` is safe to re-run.
 
**Run the pipeline** (fetch + transform, using the image's default command):
```bash
docker run --env-file .env --network <network-name> -e TFL_DB_HOST=<postgres-container-name> tfl-pipeline
```
 
A few things worth understanding about these commands:
- `--network` puts this container on the same Docker network as the Postgres container, without it, they can't reach each other by name at all.
- `-e TFL_DB_HOST=<postgres-container-name>` tells the scripts to connect to Postgres using its container name rather than `localhost`, since inside a container, `localhost` refers to the container itself, not the host machine or any other container.
- `--env-file .env` passes `DB_PASSWORD` and `TFL_API_KEY` into the container at runtime. (`.env` is excluded via `.dockerignore`).

## What's next

This project is a work in progress. Planned next steps:
- Revisiting `validityPeriods` if a concrete need for that data emerges