# AI/ML Assistant (Agentic RAG)

An agentic RAG system built with LangGraph. It answers questions about five ML papers (Transformer, BERT, LoRA, QLoRA, RAG), decides when to search the papers vs. the web, grades its own retrieved chunks, rewrites weak queries, and checks its answers before returning them.

[FILL IN: screenshot or GIF of the Streamlit app]

## Architecture

[FILL IN: paste the contents of graph.mmd inside a mermaid code block]

- **Router** picks one of: papers, web search, or direct answer.
- **Retriever** fetches the top 4 chunks (ChromaDB, all-MiniLM-L6-v2 embeddings).
- **Document grader** (LLM) removes irrelevant chunks.
- **Query rewriter** reformulates the query and retries (max 2 retries).
- **Web search fallback** (DuckDuckGo) if the papers have nothing relevant.
- **Answer checker** verifies the answer is grounded in the context and actually answers the question.
- **Give-up path** returns an honest "I couldn't find a reliable answer" instead of guessing.

## Setup

1. Create a virtual environment and install: `pip install -r requirements.txt`
2. Put the PDFs in `papers/` (arXiv: 1706.03762, 1810.04805, 2106.09685, 2305.14314, 2005.11401).
3. Set your key: `$env:GOOGLE_API_KEY="..."` (free key from Google AI Studio).
4. Index the papers: `python ingest.py`
5. Run: `streamlit run app.py` (or `python agent.py` for the command line).

## Evaluation

I compared plain RAG against this agent on [FILL IN: N] hand-written questions in four types (factual, vague, out-of-scope, multi-part). Answers were graded by an LLM judge against reference answers.

[FILL IN: paste your summary table from python eval.py summary]

Key findings:
- [FILL IN: where the agent helped, with numbers]
- [FILL IN: where it did not help]
- [FILL IN: latency and cost trade-off, e.g. the agent was Nx slower]

Judge reliability: I manually checked [FILL IN: N] verdicts and agreed with [FILL IN: N] of them.

## What failed and what I changed

- Web search initially returned 0 results because of a renamed package (duckduckgo_search to ddgs).
- A failed web question fell back to searching the papers. Fixed by routing it straight to the give-up path.
- The answer checker marked refusals as useful. Fixed by adding an explicit rule to its prompt.
- [FILL IN: your own findings from experiments.md, e.g. chunk size experiments]

## Limitations

- No conversation memory, so follow-ups like "what about its limits?" fail.
- Comparison questions can retrieve chunks from only one paper.
- Web results are short snippets, not full pages.
- Small test set, hand-written references, and an LLM judge from the same model family as the answerer.

## Possible next steps

- Hybrid search (BM25 + vectors) and a cross-encoder reranker.
- Split comparison questions into one retrieval per topic.
- Chat history in the query rewriter.
- Fetch full text of web results.
- Deploy with FastAPI + Docker.
