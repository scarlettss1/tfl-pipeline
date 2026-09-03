/*
schema.sql

Schema definitions for the TfL pipeline project's Postgres database.
This is the single source of truth for table structure, run against
the 'tfl_pipeline' database via create_tables.py, not executed directly.

All CREATE TABLE statements use IF NOT EXISTS, so this file is safe to
re-run without dropping or duplicating existing tables.
*/

-- Raw landing table: stores each TfL API poll exactly as received,
-- before any cleaning. One row = one full API response, captured at
-- one point in time. No UNIQUE constraint, every poll is a new fact
-- worth keeping, so this table just accumulates rows indefinitely.
CREATE TABLE IF NOT EXISTS raw_snapshots (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source          TEXT NOT NULL DEFAULT 'tfl_line_status_tube',
    raw_response    JSONB NOT NULL
);


-- Cleaned/transformed table: one row per line per snapshot, with only
-- the fields useful for querying trends over time. Derived entirely
-- from raw_snapshots, can be dropped and rebuilt from raw data if the
-- transform logic changes, since raw_snapshots is the permanent record.
--
-- reason and category are nullable, since a line with "Good Service"
-- has no disruption and therefore no reason/category in the source data.
--
-- Deliberately excluded: validityPeriods (fromDate/toDate/isNow), this
-- is a nested list-within-a-list in the source JSON and doesn't fit
-- cleanly as flat columns; revisit if a real need for it comes up.
CREATE TABLE IF NOT EXISTS clean_line_status (
    snapshot_id                 INTEGER NOT NULL REFERENCES raw_snapshots(id),
    line_id                     TEXT NOT NULL,
    line_name                   TEXT NOT NULL,
    status_severity              INT NOT NULL,
    status_severity_description TEXT NOT NULL,
    reason                      TEXT,
    category                    TEXT,

    PRIMARY KEY (snapshot_id, line_id)
);