import streamlit as st
from src.rag import answer_question

st.set_page_config(page_title="SEC 10-K RAG Assistant", layout="wide")

st.title("NVIDIA (NVDA) 10-K RAG Assistant")
st.caption("Backed by PostgreSQL + pgvector | Strict citations & refusal guardrails")

with st.sidebar:
    st.header("Retrieval Settings")
    top_k = st.slider("Top-K Chunks to Retrieve", min_value=1, max_value=10, value=5)

    st.divider()
    st.subheader("Sample Questions")
    sample_questions = [
        "What are NVIDIA's reportable operating segments and what does each include?",
        "What was NVIDIA's total revenue and Data Center revenue in the latest fiscal year?",
        "What are the main supply chain and manufacturing risks NVIDIA faces?",
        "What was Apple's iPhone revenue in 2025? (Refusal Test)",
    ]
    selected_sample = None
    for sq in sample_questions:
        if st.button(sq, use_container_width=True):
            selected_sample = sq

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant" and "details" in msg:
            details = msg["details"]
            if details["is_refusal"]:
                st.warning("Refusal Triggered: Answer not found in retrieved 10-K chunks.")
            else:
                st.success(f"Cited Chunks: {details['cited_chunk_indices']}")

            with st.expander("Inspect Retrieved 10-K Chunks (PostgreSQL + pgvector)"):
                for c in details["retrieved_chunks"]:
                    is_cited = c["chunk_index"] in details["cited_chunk_indices"]
                    badge = "[CITED]" if is_cited else "[Retrieved - Unused]"
                    st.markdown(
                        f"**{badge} | [{c['ticker']} {c['form']}, Chunk {c['chunk_index']}] "
                        f"-- Similarity: `{c['similarity']}`**"
                    )
                    st.text(c["content"])
                    st.divider()

user_query = st.chat_input("Ask a question about NVIDIA's Form 10-K...") or selected_sample

if user_query:
    st.session_state.messages.append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.chat_message("assistant"):
        with st.spinner("Searching pgvector & verifying citations..."):
            result = answer_question(user_query, top_k=top_k)

        st.markdown(result["answer"])
        if result["is_refusal"]:
            st.warning("Refusal Triggered: Answer not found in retrieved 10-K chunks.")
        else:
            st.success(f"Cited Chunks: {result['cited_chunk_indices']}")

        with st.expander("Inspect Retrieved 10-K Chunks (PostgreSQL + pgvector)"):
            for c in result["retrieved_chunks"]:
                is_cited = c["chunk_index"] in result["cited_chunk_indices"]
                badge = "[CITED]" if is_cited else "[Retrieved - Unused]"
                st.markdown(
                    f"**{badge} | [{c['ticker']} {c['form']}, Chunk {c['chunk_index']}] "
                    f"-- Similarity: `{c['similarity']}`**"
                )
                st.text(c["content"])
                st.divider()

    st.session_state.messages.append({
        "role": "assistant",
        "content": result["answer"],
        "details": result,
    })
