import json
import time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel, Field
from src.rag import answer_question

load_dotenv()

QUESTIONS_PATH = Path("eval/questions.json")
RESULTS_MD_PATH = Path("eval/results.md")
JUDGE_MODEL = "gpt-4.1-mini"


class JudgeVerdict(BaseModel):
    passed: bool = Field(description="True if the RAG response accurately satisfies expected_facts (or properly refuses when should_refuse is True).")
    reason: str = Field(description="Brief 1-sentence explanation of why it passed or failed.")


def grade_response(client: OpenAI, item: dict, rag_result: dict) -> JudgeVerdict:
    # Fast check for refusal questions
    if item["should_refuse"]:
        passed = rag_result["is_refusal"] is True
        reason = "Correctly refused out-of-scope question." if passed else "Failed to refuse out-of-scope question."
        return JudgeVerdict(passed=passed, reason=reason)

    # If it shouldn't refuse, but it did refuse, that's a retrieval or generation miss
    if rag_result["is_refusal"]:
        return JudgeVerdict(passed=False, reason="RAG refused to answer an in-scope question (likely missing from top-k chunks).")

    prompt = f"""You are grading a RAG system over NVIDIA's 10-K filing.
Question: {item['question']}
Expected Facts Rubric: {item['expected_facts']}
RAG System Answer: {rag_result['answer']}

Did the RAG System Answer accurately answer the question in alignment with the Expected Facts Rubric and include a citation?"""

    resp = client.beta.chat.completions.parse(
        model=JUDGE_MODEL,
        messages=[{"role": "user", "content": prompt}],
        response_format=JudgeVerdict,
        temperature=0.0,
    )
    return resp.choices[0].message.parsed


def main():
    questions = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8-sig"))
    client = OpenAI()

    rows = []
    passed_count = 0
    total_latency = 0.0

    print(f"Running evaluation on {len(questions)} questions...\n")

    for q in questions:
        t0 = time.perf_counter()
        rag_result = answer_question(q["question"], top_k=5)
        latency = round(time.perf_counter() - t0, 2)
        total_latency += latency

        verdict = grade_response(client, q, rag_result)
        if verdict.passed:
            passed_count += 1

        status = "PASS" if verdict.passed else "FAIL"
        cited = str(rag_result["cited_chunk_indices"])
        print(f"[{q['id']}] {status} ({latency}s) | Cited: {cited} | {q['question']}")
        if not verdict.passed:
            print(f"     -> Reason: {verdict.reason}")

        rows.append({
            "id": q["id"],
            "category": q["category"],
            "question": q["question"],
            "status": status,
            "cited": cited,
            "latency": f"{latency}s",
            "reason": verdict.reason,
        })

    accuracy = round((passed_count / len(questions)) * 100, 1)
    avg_latency = round(total_latency / len(questions), 2)

    # Save Markdown table to eval/results.md
    md_lines = [
        "# Mini Evaluation Results (15 Questions)",
        "",
        f"- **Overall Accuracy:** {passed_count}/{len(questions)} ({accuracy}%)",
        f"- **Average Latency:** {avg_latency}s per query",
        "",
        "| ID | Category | Question | Result | Cited Chunks | Latency | Judge Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        md_lines.append(
            f"| {r['id']} | {r['category']} | {r['question']} | **{r['status']}** | `{r['cited']}` | {r['latency']} | {r['reason']} |"
        )

    RESULTS_MD_PATH.write_text("\n".join(md_lines) + "\n", encoding="utf-8-sig")

    print("\n" + "=" * 60)
    print(f"EVAL COMPLETE: {passed_count}/{len(questions)} PASSED ({accuracy}%) | Avg Latency: {avg_latency}s")
    print(f"Saved Markdown scorecard to: {RESULTS_MD_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
