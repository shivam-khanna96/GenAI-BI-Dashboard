import sqlite3
from sqlalchemy import create_engine
from langchain_community.utilities import SQLDatabase

DB_FILE = "sample_sales.db"
db_engine = create_engine(f"sqlite:///{DB_FILE}")
db = SQLDatabase(engine=db_engine)

def extract_db_schema(db_file):
    conn = sqlite3.connect(db_file)
    cursor = conn.cursor()
    schema = {}
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table});")
            columns = [{"name": col[1], "type": col[2]} for col in cursor.fetchall()]
            schema[table] = columns
    finally:
        conn.close()
    return schema

DB_SCHEMA = extract_db_schema(DB_FILE)
