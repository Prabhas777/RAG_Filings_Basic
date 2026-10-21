import os
import psycopg
from dotenv import load_dotenv
from openai import OpenAI
from pgvector.psycopg import register_vector
from pydantic import BaseModel, Field

load_dotenv()

EMBEDDING_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4.1-mini"

SYSTEM_PROMPT = """You are a strict financial analyst assistant answering questions about SEC 10-K filings.
Use ONLY the provided context chunks to answer the user's question.

Rules:
1. Every factual claim or number MUST include an inline citation like [NVDA 10-K, Chunk X].
2. If the provided chunks do not contain enough information to answer the question, set is_refusal=True, leave cited_chunk_indices empty, and state clearly what information is missing from the retrieved context.
3. Never guess, extrapolate, or use outside knowledge."""


class RAGResponse(BaseModel):
    answer: str = Field(description="The final answer with inline citations like [NVDA 10-K, Chunk X], or a clear refusal message.")
    cited_chunk_indices: list[int] = Field(description="List of chunk_index integers that directly supported the answer.")
    is_refusal: bool = Field(description="True if the context did not contain the answer and you had to refuse.")


def retrieve_chunks(question: str, top_k: int = 5) -> list[dict]:
    client = OpenAI()
    db_url = os.getenv("DATABASE_URL")

    # 1. Embed the user's question
    q_emb = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=question
    ).data[0].embedding

    # 2. Search pgvector using Cosine Distance (<=>)
    with psycopg.connect(db_url) as conn:
        register_vector(conn)
        rows = conn.execute(
            """
            SELECT ticker, form, chunk_index, content,
                   1 - (embedding <=> %s::vector) AS similarity
            FROM filing_chunks
            ORDER BY embedding <=> %s::vector
            LIMIT %s
            """,
            (q_emb, q_emb, top_k),
        ).fetchall()

    return [
        {
            "ticker": r[0],
            "form": r[1],
            "chunk_index": r[2],
            "content": r[3],
            "similarity": round(float(r[4]), 4),
        }
        for r in rows
    ]


def answer_question(question: str, top_k: int = 5) -> dict:
    client = OpenAI()
    chunks = retrieve_chunks(question, top_k=top_k)

    # Format the retrieved chunks for the prompt
    context_str = "\n\n---\n\n".join(
        f"[{c['ticker']} {c['form']}, Chunk {c['chunk_index']}] (Similarity: {c['similarity']})\n{c['content']}"
        for c in chunks
    )

    response = client.beta.chat.completions.parse(
        model=CHAT_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context Chunks:\n{context_str}\n\nQuestion: {question}"},
        ],
        response_format=RAGResponse,
        temperature=0.0,
    )

    parsed: RAGResponse = response.choices[0].message.parsed
    return {
        "question": question,
        "answer": parsed.answer,
        "cited_chunk_indices": parsed.cited_chunk_indices,
        "is_refusal": parsed.is_refusal,
        "retrieved_chunks": chunks,
    }


if __name__ == "__main__":
    test_questions = [
        "What are NVIDIA's reportable operating segments and what does each include?",
        "What was Apple's iPhone revenue in 2025?",  # Should trigger a refusal!
    ]

    for q in test_questions:
        print("=" * 70)
        print(f"QUESTION: {q}")
        result = answer_question(q, top_k=5)
        print(f"RETRIEVED CHUNKS: {[c['chunk_index'] for c in result['retrieved_chunks']]}")
        print(f"IS REFUSAL: {result['is_refusal']}")
        print(f"CITED CHUNKS: {result['cited_chunk_indices']}")
        print(f"\nANSWER:\n{result['answer']}\n")
