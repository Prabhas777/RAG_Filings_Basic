import json
import os
from pathlib import Path
import psycopg
from dotenv import load_dotenv
from openai import OpenAI
from pgvector.psycopg import register_vector

load_dotenv()

CHUNKS_PATH = Path("data/processed/chunks.json")
EMBEDDING_MODEL = "text-embedding-3-small"
BATCH_SIZE = 50


def get_embeddings(client: OpenAI, texts: list[str]) -> list[list[float]]:
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts
    )
    return [item.embedding for item in response.data]


def main():
    if not CHUNKS_PATH.exists():
        raise FileNotFoundError(f"Chunks file not found at {CHUNKS_PATH}. Run src/ingest.py first.")

    chunks = json.loads(CHUNKS_PATH.read_text(encoding="utf-8"))
    print(f"1. Loaded {len(chunks)} chunks from {CHUNKS_PATH}")

    client = OpenAI()
    db_url = os.getenv("DATABASE_URL")

    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        register_vector(conn)

        print("2. Creating 'filing_chunks' table in Postgres...")
        conn.execute("DROP TABLE IF EXISTS filing_chunks")
        conn.execute("""
            CREATE TABLE filing_chunks (
                id serial PRIMARY KEY,
                ticker text NOT NULL,
                form text NOT NULL,
                chunk_index integer NOT NULL,
                source_file text NOT NULL,
                content text NOT NULL,
                embedding vector(1536) NOT NULL
            )
        """)

        print(f"3. Embedding and inserting {len(chunks)} chunks in batches of {BATCH_SIZE}...")
        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i : i + BATCH_SIZE]
            texts = [c["content"] for c in batch]
            embeddings = get_embeddings(client, texts)

            with conn.cursor() as cur:
                for chunk, emb in zip(batch, embeddings):
                    cur.execute(
                        """
                        INSERT INTO filing_chunks
                            (ticker, form, chunk_index, source_file, content, embedding)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            chunk["ticker"],
                            chunk["form"],
                            chunk["chunk_index"],
                            chunk["source_file"],
                            chunk["content"],
                            emb,
                        ),
                    )
            print(f"   Inserted chunks {i} to {i + len(batch) - 1}")

        count = conn.execute("SELECT COUNT(*) FROM filing_chunks").fetchone()[0]
        print(f"\n--- Step 3 Complete! Total rows in 'filing_chunks': {count} ---")


if __name__ == "__main__":
    main()
