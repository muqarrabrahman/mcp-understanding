import os
import pathlib

import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.environ["DB_HOST"],
    port=os.environ["DB_PORT"],
    dbname=os.environ["DB_NAME"],
    user=os.environ["DB_USER"],
    password=os.environ["DB_PASSWORD"],
)
conn.autocommit = True

sql = pathlib.Path(__file__).parent.joinpath("schema.sql").read_text()

with conn.cursor() as cur:
    cur.execute(sql)

print("Schema applied successfully.")
conn.close()
