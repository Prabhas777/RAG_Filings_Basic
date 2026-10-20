import json
import os
import re
from pathlib import Path
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from sec_edgar_downloader import Downloader

load_dotenv()

RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
TICKER = "NVDA"


def download_latest_10k(ticker: str) -> Path:
    user_agent = os.getenv("SEC_USER_AGENT", "PortfolioApp contact@example.com")
    name, email = user_agent.rsplit(" ", 1)

    print(f"1. Downloading latest 10-K for {ticker} from SEC EDGAR...")
    dl = Downloader(name, email, str(RAW_DIR))
    dl.get("10-K", ticker, limit=1, download_details=True)

    # Locate the downloaded primary HTML document (or full submission text)
    filing_dir = RAW_DIR / "sec-edgar-filings" / ticker / "10-K"
    html_files = list(filing_dir.rglob("*.htm*"))
    if html_files:
        return html_files[0]
    txt_files = list(filing_dir.rglob("*.txt"))
    if txt_files:
        return txt_files[0]
    raise FileNotFoundError(f"Could not find downloaded 10-K in {filing_dir}")


def extract_clean_text(file_path: Path) -> str:
    print(f"2. Cleaning HTML from {file_path.name} (this takes ~10-20 seconds)...")
    raw_html = file_path.read_text(encoding="utf-8", errors="ignore")

    # If it's a full-submission.txt, keep only the main 10-K <DOCUMENT> block
    if file_path.suffix == ".txt" and "<DOCUMENT>" in raw_html:
        raw_html = raw_html.split("<DOCUMENT>")[1].split("</DOCUMENT>")[0]

    soup = BeautifulSoup(raw_html, "lxml")

    # Remove invisible script/style tags
    for tag in soup(["script", "style", "ix:header", "ix:hidden"]):
        tag.decompose()

    text = soup.get_text(separator="\n")

    # Collapse excessive blank lines and spaces
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def chunk_text(text: str, ticker: str, source_file: str, chunk_size: int = 2000, overlap: int = 200) -> list[dict]:
    print(f"3. Splitting text ({len(text):,} characters) into chunks...")
    chunks = []
    start = 0
    chunk_index = 0

    while start < len(text):
        end = start + chunk_size
        chunk_str = text[start:end].strip()

        if chunk_str:
            chunks.append({
                "chunk_index": chunk_index,
                "ticker": ticker,
                "form": "10-K",
                "source_file": source_file,
                "content": chunk_str,
            })
            chunk_index += 1

        start += chunk_size - overlap

    return chunks


if __name__ == "__main__":
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    filing_path = download_latest_10k(TICKER)
    clean_text = extract_clean_text(filing_path)

    # Save clean text so we can inspect it
    clean_path = PROCESSED_DIR / f"{TICKER}_10K_clean.txt"
    clean_path.write_text(clean_text, encoding="utf-8")

    # Create and save chunks
    chunks = chunk_text(clean_text, TICKER, filing_path.name)
    chunks_path = PROCESSED_DIR / "chunks.json"
    chunks_path.write_text(json.dumps(chunks, indent=2), encoding="utf-8")

    print("\n--- Step 2 Summary ---")
    print(f"Saved clean text to: {clean_path}")
    print(f"Saved {len(chunks)} chunks to: {chunks_path}")
    print("\nSample Chunk #10 preview:")
    print(chunks[10]["content"][:300] + "...")
