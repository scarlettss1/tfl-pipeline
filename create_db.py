import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()
db_password = os.getenv("DB_PASSWORD")

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    dbname="postgres",
    user="postgres",
    password=db_password 
)
conn.autocommit = True
cur = conn.cursor()
cur.execute("CREATE DATABASE tfl_pipeline")
cur.close()
conn.close()

print("Database created!")