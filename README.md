## 🎥 Video Walkthrough & Live UI
👉 **[Watch the 2-Minute Architecture & Evaluation Walkthrough on Loom](https://www.loom.com/share/03dad793f66c40f18ae47c240447a58e)**

<img width="1375" height="741" alt="image" src="https://github.com/user-attachments/assets/e6e7d621-a47c-4198-87cf-62b102a9dcc3" />


# NVIDIA 10-K RAG Assistant

This project is a question-answering system built in Python for NVIDIA's (`NVDA`) annual SEC Form 10-K report. It uses **PostgreSQL with pgvector** to store and search document chunks, **OpenAI** for embeddings and answers, **Pydantic** to enforce citations, and **Streamlit** for the web interface. It also includes an automated evaluation script that grades the system on 15 test questions.

## Video Walkthrough
**[Watch the 2-Minute Project Walkthrough on Loom](PASTE_YOUR_LOOM_LINK_HERE)**

## How It Works

```text
SEC EDGAR (NVDA 10-K HTML)
   |
   v  src/ingest.py (Cleans HTML with BeautifulSoup4 and splits into 2,000-char chunks)
190 Text Chunks (data/processed/chunks.json)
   |
   v  src/embed_store.py (Creates 1,536-number vectors with text-embedding-3-small)
PostgreSQL 16 + pgvector (Running in Docker)
   |
   v  src/rag.py (Finds top 5 chunks using cosine similarity and sends to gpt-4.1-mini)
Structured Answer { answer, cited_chunk_indices, is_refusal }
   |
   +--> app.py (Streamlit web app showing answers and retrieved source chunks)
   +--> src/evaluate.py (Automated grading script across 15 test questions)
```

1. **Download and Chunk (`src/ingest.py`):** Downloads NVIDIA's latest 10-K filing from the SEC EDGAR database, strips out the HTML tags using BeautifulSoup, and splits the 341,000 characters of text into 190 chunks. Each chunk is 2,000 characters long with a 200-character overlap so sentences are not cut off in the middle.
2. **Embed and Store (`src/embed_store.py`):** Sends all 190 text chunks to OpenAI's `text-embedding-3-small` model to convert each chunk into a vector of 1,536 numbers. Both the text and the vectors are stored in a PostgreSQL database using the `pgvector` extension.
3. **Search and Answer (`src/rag.py`):** When a user asks a question, the script converts the question into a vector and runs a SQL query using the `<=>` cosine distance operator to find the 5 closest chunks in the database. Those 5 chunks are sent to `gpt-4.1-mini` with a Pydantic schema that requires inline citations (like `[NVDA 10-K, Chunk 179]`) or triggers a refusal if the answer is not in the retrieved text.
4. **Web Interface (`app.py`):** A Streamlit chat page where users can ask questions, see which chunks were cited, and expand a dropdown to read the exact paragraphs pulled from the database.
5. **Automated Evaluation (`src/evaluate.py`):** Runs 15 test questions (12 factual/financial questions and 3 out-of-scope trick questions) and grades whether the system returned the right facts and citations.

---

## Evaluation Results (15 Questions)

- **Overall Score:** 13/15 (86.7%)
- **Refusal Score (Out-of-Scope Questions):** 3/3 (100%)
- **Average Response Time:** 2.03s per question

| ID | Category | Question | Result | Cited Chunks | Time | Notes |
|---|---|---|---|---|---|---|
| Q1 | fact | What are NVIDIA's two reportable operating segments? | **PASS** | `[179, 10, 102]` | 5.94s | Correctly listed Compute & Networking and Graphics with citations. |
| Q2 | fact | What products and platforms are included in the Graphics segment? | **FAIL** | `[179]` | 1.26s | Missed 'GeForce NOW game streaming' because only the footnote chunk (179) was retrieved, missing the overview chunk from the start of the report. |
| Q3 | fact | What platforms are included in the Compute & Networking segment? | **PASS** | `[179]` | 1.76s | Correctly listed Data Center, AI software, and Automotive platforms. |
| Q4 | numeric | What was NVIDIA's total revenue in the latest fiscal year reported in this 10-K? | **PASS** | `[134]` | 1.62s | Returned the exact total revenue figure with citation. |
| Q5 | numeric | What was NVIDIA's Data Center revenue in the latest fiscal year reported in this 10-K? | **PASS** | `[182]` | 1.45s | Returned the exact Data Center revenue figure with citation. |
| Q6 | fact | Which third-party foundries manufacture NVIDIA's semiconductor wafers? | **PASS** | `[20]` | 1.53s | Identified TSMC and Samsung Electronics with citation. |
| Q7 | fact | What is CUDA and how does it fit into NVIDIA's platform strategy? | **PASS** | `[7, 12, 15]` | 2.01s | Explained the CUDA programming model and platform strategy with citations. |
| Q8 | risk | How do US government export controls impact NVIDIA's business in China? | **PASS** | `[74, 79, 81, 82]` | 4.22s | Explained export licensing restrictions on data center GPUs to China. |
| Q9 | numeric | How many employees did NVIDIA have at the end of the latest fiscal year? | **FAIL** | `[29]` | 1.36s | Found the right employee count in Chunk 29, but failed the rubric because the chunk did not keep the 'Item 1' section title. |
| Q10 | fact | Where is NVIDIA's corporate headquarters located? | **PASS** | `[10, 103, 102]` | 1.52s | Identified Santa Clara, California with citations. |
| Q11 | numeric | What was NVIDIA's gross margin percentage in the latest fiscal year? | **PASS** | `[111]` | 1.46s | Reported the exact gross margin percentage with citation. |
| Q12 | fact | What networking interconnect technologies does NVIDIA offer for AI data centers? | **PASS** | `[11, 12]` | 2.06s | Listed NVLink, InfiniBand, and Spectrum Ethernet with citations. |
| Q13 | refusal | What was Apple's iPhone revenue in 2025? | **PASS** | `[]` | 1.46s | Refused to answer because Apple is not in the filing. |
| Q14 | refusal | What was NVIDIA's intraday stock price at 2:15 PM on October 15, 2026? | **PASS** | `[]` | 1.19s | Refused to answer because daily stock prices are not in the filing. |
| Q15 | refusal | How many Bitcoin does NVIDIA hold on its balance sheet? | **PASS** | `[]` | 1.56s | Refused to answer because Bitcoin is not mentioned in the filing. |

---

## What Failed and How to Fix It Next

1. **Question 2 Failure (Missing details from another part of the report):**
   - **What happened:** Vector search grabbed the top 5 chunks, which included Chunk 179 (the financial footnote at the end of the report). That chunk listed GeForce and RTX GPUs, but left out *GeForce NOW game streaming*, which was mentioned earlier in the business overview section.
   - **How to fix it:** Combine keyword search (BM25) with vector search and add a reranker that checks the top 25 chunks before picking the best 5.

2. **Question 9 Failure (Missing section headers in metadata):**
   - **What happened:** The system found the right employee count in Chunk 29, but the test rubric required a citation to *Item 1*. Because the text was chopped every 2,000 characters after stripping the HTML, the section headers were lost and the citation only said `[NVDA 10-K, Chunk 29]`.
   - **How to fix it:** Parse the HTML structure before chunking so each chunk saves its SEC section header (like `Item 1`, `Item 1A`, `Item 7`) in the database, and keep HTML tables intact as Markdown.

---

## How to Run Locally

### 1. Start PostgreSQL with pgvector
```powershell
docker compose up -d
```

### 2. Install Packages and Set Environment Variables
```powershell
uv sync
Copy-Item .env.example .env
# Add your OPENAI_API_KEY and SEC_USER_AGENT to .env
```

### 3. Download Data, Store Embeddings, and Start the App
```powershell
python src/ingest.py
python src/embed_store.py
streamlit run app.py
```

### 4. Run the Evaluation Script
```powershell
python -m src.evaluate
```
