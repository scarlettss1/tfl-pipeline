"""
transform_status.py

Reads raw TfL API snapshots from raw_snapshots that haven't been
processed yet, extracts the useful fields from each line's status,
and inserts one row per line into clean_line_status.

Meant to be run after fetch_status.py has collected new snapshots,
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
from transform_logic import extract_line_fields
import os

load_dotenv()
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("TFL_DB_HOST", "localhost")

conn = psycopg2.connect(
    host=db_host,
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
        # raw_response is already a Python list of dicts, psycopg2
        # converts JSONB back automatically, no json.loads() needed.
        for line in raw_response:
            fields = extract_line_fields(line)

            cur.execute("""
                INSERT INTO clean_line_status
                    (snapshot_id, line_id, line_name, status_severity,
                     status_severity_description, reason, category)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (snapshot_id, fields["line_id"], fields["line_name"],
                  fields["status_severity"], fields["status_severity_description"],
                  fields["reason"], fields["category"]))

            rows_inserted += 1

    conn.commit()
    print(f"Transformed {len(new_snapshots)} snapshot(s), inserted {rows_inserted} row(s).")

except (psycopg2.Error, KeyError) as e:
    print(f"Transform failed: {e}")
    conn.rollback()
finally:
    cur.close()
    conn.close()