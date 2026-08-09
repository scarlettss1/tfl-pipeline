"""
create_db.py

One-time setup script for the TfL pipeline project.

Creates the 'tfl_pipeline' database inside the local Postgres container.
This is meant to be run once, manually - not as part of the recurring
pipeline. Running it a second time will fail, since Postgres has no
built-in "CREATE DATABASE IF NOT EXISTS".

Prerequisites:
- Docker container 'test-postgres' must be running
- A .env file must exist in this folder, containing DB_PASSWORD=<password>
"""

import psycopg2
import os
from dotenv import load_dotenv

# Load DB_PASSWORD from .env rather than hardcoding it, so the real
# password never ends up committed to Git history.
load_dotenv()
db_password = os.getenv("DB_PASSWORD")

# Connect to the default 'postgres' database first - a connection can't
# create the database it's connected to, so this has to target a
# different, already-existing one.
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="postgres",
    user="postgres",
    password=db_password 
)

# CREATE DATABASE can't run inside Postgres's normal transaction mode,
# so autocommit must be enabled specifically for this command to work.
conn.autocommit = True

cur = conn.cursor()
cur.execute("CREATE DATABASE tfl_pipeline")
cur.close()
conn.close()

print("Database created!")