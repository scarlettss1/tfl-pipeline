/*
schema.sql

Schema definitions for the TfL pipeline project's Postgres database.
This is the single source of truth for table structure - run against
the 'tfl_pipeline' database via create_tables.py, not executed directly.

All CREATE TABLE statements use IF NOT EXISTS, so this file is safe to
re-run without dropping or duplicating existing tables.
*/

-- Raw landing table: stores each TfL API poll exactly as received,
-- before any cleaning. One row = one full API response, captured at
-- one point in time. No UNIQUE constraint - every poll is a new fact
-- worth keeping, so this table just accumulates rows indefinitely.
CREATE TABLE IF NOT EXISTS raw_snapshots (
    id              INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    captured_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    source          TEXT NOT NULL DEFAULT 'tfl_line_status_tube',
    raw_response    JSONB NOT NULL
);