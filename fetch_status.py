"""
fetch_status.py

Fetches the current status of all Tube lines from the TfL Unified API
and stores the raw JSON response as a new row in raw_snapshots.

Meant to be run repeatedly (e.g. every 10-15 minutes via a scheduler),
building up a time series of Tube line status over time. Each run adds
one new row, it never updates or deletes existing rows.

Prerequisites:
- Docker container 'test-postgres' must be running
- The 'tfl_pipeline' database and raw_snapshots table must already exist
  (run create_db.py and create_tables.py first)
- A .env file must exist in this folder, containing DB_PASSWORD and
  TFL_API_KEY
"""

import requests
import psycopg2
from dotenv import load_dotenv
import os
import json
import sys

load_dotenv()

tfl_api_key = os.getenv("TFL_API_KEY")
db_password = os.getenv("DB_PASSWORD")
db_host = os.getenv("DB_HOST", "localhost")

# Step 1: Call the TfL API
url = "https://api.tfl.gov.uk/Line/Mode/tube/Status"
params = {"app_key": tfl_api_key}

try:
    response = requests.get(url, params=params)
    response.raise_for_status()  # raises an error if status is 4xx/5xx
    data = response.json()  # turns the response body into a Python object (a list of dictionaries,  
                            # each dictionary representing one line's status info)
except requests.exceptions.RequestException as e:
    print(f"Failed to fetch TfL data: {e}")
    sys.exit(1)  # stop the script here, no point trying the DB step

# Step 2: Connect to the database and insert the raw response
conn = psycopg2.connect(
    host=db_host,
    port=5432,
    dbname="tfl_pipeline",
    user="postgres",
    password=db_password
)
cur = conn.cursor()

try:
    cur.execute(
        "INSERT INTO raw_snapshots (raw_response) VALUES (%s)",
        (json.dumps(data),) # Convert Python object to a JSON-formatted string, since psycopg2
                            # can't insert a raw Python list/dict into a JSONB column directly
    )
    conn.commit()
    print("Snapshot saved!")
except psycopg2.Error as e:
    print(f"Failed to insert snapshot: {e}")
    conn.rollback()  # undo any partial changes on this connection
finally:
    cur.close()
    conn.close()