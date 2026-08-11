"""
transform_status.py

Reads raw TfL API snapshots from raw_snapshots that haven't been
processed yet, extracts the useful fields from each line's status,
and inserts one row per line into clean_line_status.

Meant to be run after fetch_status.py has collected new snapshots -
either manually, or later as a scheduled step in the same pipeline.
Safe to re-run: only processes snapshots not already present in
clean_line_status, so it never creates duplicates.

Prerequisites:
- Docker container 'test-postgres' must be running
- The 'tfl_pipeline' database and both tables must already exist
  (run create_db.py and create_tables.py first)
- A .env file must exist in this folder, containing DB_PASSWORD
"""

import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()
db_password = os.getenv("DB_PASSWORD")

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="tfl_pipeline",
    user="postgres",
    password=db_password
)
cur = conn.cursor()

try:
    # Only pull snapshots that haven't been transformed yet, so
    # re-running this script never creates duplicate rows.
    cur.execute("""
        SELECT id, raw_response
        FROM raw_snapshots
        WHERE id NOT IN (SELECT DISTINCT snapshot_id FROM clean_line_status)
    """)
    new_snapshots = cur.fetchall()

    rows_inserted = 0

    for snapshot_id, raw_response in new_snapshots:
        # raw_response is already a Python list of dicts - psycopg2
        # converts JSONB back automatically, no json.loads() needed.
        for line in raw_response:
            line_id = line["id"]
            line_name = line["name"]

            # lineStatuses is itself a list, but TfL only ever returns
            # one entry per line for this endpoint - we take the first.
            status = line["lineStatuses"][0]
            status_severity = status["statusSeverity"]
            status_severity_description = status["statusSeverityDescription"]

            # reason and category only exist in the JSON when there's an
            # active disruption, so .get() is used instead of [] - it
            # returns None if the key is missing, instead of raising an
            # error like [] would.
            reason = status.get("reason")
            category = status.get("disruption", {}).get("category")

            cur.execute("""
                INSERT INTO clean_line_status
                    (snapshot_id, line_id, line_name, status_severity,
                     status_severity_description, reason, category)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (snapshot_id, line_id, line_name, status_severity,
                  status_severity_description, reason, category))

            rows_inserted += 1

    conn.commit()
    print(f"Transformed {len(new_snapshots)} snapshot(s), inserted {rows_inserted} row(s).")

except (psycopg2.Error, KeyError) as e:
    print(f"Transform failed: {e}")
    conn.rollback()
finally:
    cur.close()
    conn.close()