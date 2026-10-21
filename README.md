# SEC 10-K Filings RAG Assistant (Baseline)

An end-to-end Retrieval-Augmented Generation (RAG) system built in Python over NVIDIA's (`NVDA`) SEC Form 10-K filing, backed by **PostgreSQL + pgvector**, **Pydantic structured citations**, **Streamlit**, and an automated **LLM-as-a-Judge evaluation harness**.

## Architecture

```text
SEC EDGAR (NVDA 10-K HTML)
   |
   v  src/ingest.py (BeautifulSoup4 + 2,000-char overlapping chunker)
190 Text Chunks (data/processed/chunks.json)
   |
   v  src/embed_store.py (text-embedding-3-small -> 1536-d vectors)
PostgreSQL 16 + pgvector (Docker container: filings-pgvector)
   |
   v  src/rag.py (Cosine distance `<=>` Top-K retrieval + gpt-4.1-mini + Pydantic)
Structured Answer { answer, cited_chunk_indices, is_refusal }
   |
   +--> app.py (Streamlit Chat UI with expandable source chunk inspector)
   +--> src/evaluate.py (15-question automated LLM-as-a-Judge evaluation)
```

## Key Features
- **Zero-Framework Transparency:** Built directly with the OpenAI SDK, `psycopg`, and `pgvector` SQL operators (`<=>`) to expose every step of the RAG pipeline.
- **Strict Inline Citations & Refusal Guardrails:** Enforces a Pydantic schema (`RAGResponse`) requiring inline `[NVDA 10-K, Chunk X]` citations for every claim and automatic refusal (`is_refusal=True`) when context is insufficient.
- **Interactive Source Verification UI:** Streamlit web app (`app.py`) highlights which retrieved chunks were actually cited vs. unused.
- **Automated Evaluation Harness:** 15 hand-curated questions across factual lookups, financial metrics, risk factors, and out-of-scope refusal traps.

---

## Mini Evaluation Results (15 Questions)

- **Overall Accuracy:** 13/15 (86.7%)
- **Refusal Accuracy (Out-of-Scope Queries):** 3/3 (100%)
- **Average Latency:** 2.03s per query

| ID | Category | Question | Result | Cited Chunks | Latency | Judge Notes |
|---|---|---|---|---|---|---|
| Q1 | fact | What are NVIDIA's two reportable operating segments? | **PASS** | `[179, 10, 102]` | 5.94s | Accurately identifies Compute & Networking and Graphics with citations. |
| Q2 | fact | What products and platforms are included in the Graphics segment? | **FAIL** | `[179]` | 1.26s | Omits 'GeForce NOW game streaming' because only the footnote chunk (179) was retrieved, missing the Item 1 overview chunk. |
| Q3 | fact | What platforms are included in the Compute & Networking segment? | **PASS** | `[179]` | 1.76s | Accurately lists Data Center, AI software, and Automotive platforms with citation. |
| Q4 | numeric | What was NVIDIA's total revenue in the latest fiscal year reported in this 10-K? | **PASS** | `[134]` | 1.62s | Accurately states total revenue with inline citation. |
| Q5 | numeric | What was NVIDIA's Data Center revenue in the latest fiscal year reported in this 10-K? | **PASS** | `[182]` | 1.45s | Accurately states Data Center revenue with inline citation. |
| Q6 | fact | Which third-party foundries manufacture NVIDIA's semiconductor wafers? | **PASS** | `[20]` | 1.53s | Accurately identifies TSMC and Samsung Electronics with citation. |
| Q7 | fact | What is CUDA and how does it fit into NVIDIA's platform strategy? | **PASS** | `[7, 12, 15]` | 2.01s | Accurately explains CUDA programming model and platform strategy with citations. |
| Q8 | risk | How do US government export controls impact NVIDIA's business in China? | **PASS** | `[74, 79, 81, 82]` | 4.22s | Accurately details export licensing restrictions on data center GPUs to China. |
| Q9 | numeric | How many employees did NVIDIA have at the end of the latest fiscal year? | **PASS/FAIL** | `[29]` | 1.36s | Found the correct headcount in Chunk 29, but naive chunking lacked the 'Item 1' section metadata label. |
| Q10 | fact | Where is NVIDIA's corporate headquarters located? | **PASS** | `[10, 103, 102]` | 1.52s | Accurately identifies Santa Clara, California with citations. |
| Q11 | numeric | What was NVIDIA's gross margin percentage in the latest fiscal year? | **PASS** | `[111]` | 1.46s | Accurately reports gross margin percentage from MD&A with citation. |
| Q12 | fact | What networking interconnect technologies does NVIDIA offer for AI data centers? | **PASS** | `[11, 12]` | 2.06s | Accurately lists NVLink, InfiniBand, and Spectrum Ethernet with citations. |
| Q13 | refusal | What was Apple's iPhone revenue in 2025? | **PASS** | `[]` | 1.46s | Correctly refused out-of-scope question. |
| Q14 | refusal | What was NVIDIA's intraday stock price at 2:15 PM on October 15, 2026? | **PASS** | `[]` | 1.19s | Correctly refused out-of-scope question. |
| Q15 | refusal | How many Bitcoin does NVIDIA hold on its balance sheet? | **PASS** | `[]` | 1.56s | Correctly refused out-of-scope question. |

---

## Documented Failure Analysis & Next Iteration Roadmap

1. **Q2 Failure (Incomplete Multi-Section Synthesis):**
   - **Root Cause:** Vector search (`top_k=5`) retrieved Chunk 179 (the segment footnote at the back of the 10-K) which listed GeForce and RTX GPUs, but missed the Item 1 business overview chunk mentioning *GeForce NOW game streaming*.
   - **Next Fix:** Implement Hybrid Search (BM25 + Dense Vector) and Cross-Encoder Reranking (`top_k=25` -> rerank to `top_k=5`).

2. **Q9 Failure (Missing Section Header Metadata):**
   - **Root Cause:** The system retrieved the exact employee headcount in Chunk 29, but because naive character chunking stripped SEC section headers, the citation only said `[NVDA 10-K, Chunk 29]` instead of `[NVDA 10-K, Item 1, Chunk 29]`.
   - **Next Fix:** Build a structure-aware HTML parser that preserves SEC `Item` headers as chunk metadata and keeps financial tables intact in Markdown.

---

## Quickstart

### 1. Start PostgreSQL + pgvector
```powershell
docker compose up -d
```

### 2. Install Dependencies & Configure Environment
```powershell
uv sync
Copy-Item .env.example .env
# Add your OPENAI_API_KEY and SEC_USER_AGENT to .env
```

### 3. Ingest, Embed, and Launch UI
```powershell
python src/ingest.py
python src/embed_store.py
streamlit run app.py
```

### 4. Run Automated Evaluation
```powershell
python -m src.evaluate
```
