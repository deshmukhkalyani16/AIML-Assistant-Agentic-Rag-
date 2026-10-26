# Experiments log

## Baseline (plain RAG, k=4, chunk size 800, overlap 150)

* QLoRA memory question: correct, cited, 4 chunks from qlora.pdf.
* LoRA vs QLoRA comparison: all 4 chunks from qlora.pdf, none from lora.pdf. Partial answer.
* Vague question ("what about its limits?"): retrieved unrelated pages, refused honestly.
* Out-of-scope question (2024 election): retrieved irrelevant chunks, refused honestly.

Takeaway: the baseline is honest, but it fails on multi-paper comparisons, vague queries, and questions outside the papers.

* Changed chunk size to 400: retrieval got worse because definitions were split in half.
* Web route results (after fixes):
* \- Open-source LLM news question: snippets from tracker homepages had no model names, so the answer check marked it not useful and the agent gave up correctly.
* \- Easy facts (capital of Australia, Nvidia CEO): correct, cited, check passed.
* \- Limitation: web results are short snippets. Possible upgrade: fetch full page text of the top result.
* \- Router sends general-knowledge facts to web search (no general-knowledge route).
* Eval pilot (3 factual questions): baseline 0.67, agent 0.67. Agent \~6x slower (27s vs 4s).
* One question scored 0 for both systems; agent gave up. Cause: \[fill in after reading the answers].

