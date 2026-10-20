import os
import psycopg
from dotenv import load_dotenv
from pgvector.psycopg import register_vector

load_dotenv()
db_url = os.getenv("DATABASE_URL")

with psycopg.connect(db_url, autocommit=True) as conn:
    conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
    register_vector(conn)

    conn.execute("DROP TABLE IF EXISTS test_items")
    conn.execute("CREATE TABLE test_items (id serial PRIMARY KEY, content text, embedding vector(3))")

    conn.execute(
        "INSERT INTO test_items (content, embedding) VALUES (%s, %s)",
        ("hello world", [0.1, 0.2, 0.3])
    )

    row = conn.execute("SELECT id, content, embedding FROM test_items").fetchone()
    print(f"Read back from Postgres -> ID: {row[0]}, Content: '{row[1]}', Vector: {row[2]}")

    conn.execute("DROP TABLE test_items")
    print("Database vector check passed and test table dropped!")
