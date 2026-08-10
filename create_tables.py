"""
create_tables.py

One-time setup script for the TfL pipeline project.

Creates all tables defined in sql/schema.sql inside the 'tfl_pipeline'
database. Currently this is just 'raw_snapshots', the landing table for
unprocessed TfL API responses.

Safe to run more than once: schema.sql uses CREATE TABLE IF NOT EXISTS,
so re-running this script won't error or wipe existing data if the
table already exists.

Prerequisites:
- Docker container 'test-postgres' must be running
- The 'tfl_pipeline' database must already exist (run create_db.py first)
- A .env file must exist in this folder, containing DB_PASSWORD=<password>
- sql/schema.sql must exist, containing the CREATE TABLE statement(s)
"""

import psycopg2
from dotenv import load_dotenv
import os

# Load DB_PASSWORD from .env rather than hardcoding it, so the real
# password never ends up committed to Git history.
load_dotenv()
db_password = os.getenv("DB_PASSWORD")

# Unlike create_db.py, this script connects directly to 'tfl_pipeline' -
# the tables we're creating live inside that database, not 'postgres'.
conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="tfl_pipeline",
    user="postgres",
    password=db_password
)

cur = conn.cursor()

# Read the schema file's contents as plain text. Keeping the CREATE TABLE
# statements in a separate .sql file (rather than a Python string) means
# the schema can be inspected or run independently of this script, and
# stays readable as more tables get added.
with open("sql/schema.sql", "r") as f:
    schema_sql = f.read()

# Unlike CREATE DATABASE, CREATE TABLE runs fine inside a normal
# transaction, so no autocommit is needed here - just a manual commit
# once everything in schema.sql has executed successfully.
cur.execute(schema_sql)
conn.commit()

cur.close()
conn.close()

print("Tables created!")