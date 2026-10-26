import re

NEW_GENERAL = r'''def page_label(d: Document) -> str:
    """PDF pages are stored 0-based; show the number a reader sees in the PDF."""
    p = d.metadata.get("page")
    return str(p + 1) if isinstance(p, int) else str(p)


def search_docs(query: str, n: int = 4) -> List[Document]:
    """Web search that returns Documents with title and url in the metadata."""
    try:
        hits = DDGS().text(query, max_results=n)
    except Exception as e:  # rate limits, network problems
        print("Web search failed:", e)
        return []
    return [
        Document(page_content=f"{h.get('title', '')}: {h.get('body', '')}",
                 metadata={"source": h.get("href", "web"), "page": "-", "title": h.get("title", "")})
        for h in hits
    ]


def general_answer(state: State):
    docs = search_docs(state["question"])
    if docs:
        context = "\n\n".join(
            f"[{i + 1}] {d.metadata.get('title', '')}: {d.page_content[:500]}"
            for i, d in enumerate(docs)
        )
        prompt = (
            "Answer this AI/ML question clearly and concisely (under 200 words). Use your general "
            "knowledge, and use the web snippets below where they help. Cite a snippet as [1], [2] "
            "only when you actually use it.\n\n"
            f"Web snippets:\n{context}\n\nQuestion: {state['question']}"
        )
        note = "\n\n*(Answered mainly from general knowledge, with web references listed under Sources.)*"
    else:
        prompt = (
            "Answer this AI/ML question clearly and concisely (under 200 words) from general knowledge.\n\n"
            f"Question: {state['question']}"
        )
        note = "\n\n*(Answered from general knowledge. No external sources were found.)*"
    answer = to_text(llm.invoke(prompt)) + note
    return {"generation": answer, "documents": docs,
            "steps": log(state, f"Answered from general knowledge with {len(docs)} web references")}
'''

s = open("agent.py", encoding="utf-8").read()
if "def search_docs" in s:
    print("agent.py: already patched")
else:
    s, n = re.subn(r"def general_answer\(state: State\):.*?(?=def direct_answer)",
                   lambda m: NEW_GENERAL + "\n\n", s, count=1, flags=re.S)
    print("agent.py: general route with web sources", "replaced" if n else "NOT FOUND")

    old = 'metadata={"source": h.get("href", "web"), "page": "-"})'
    if old in s:
        s = s.replace(old, 'metadata={"source": h.get("href", "web"), "page": "-", "title": h.get("title", "")})', 1)
        print("agent.py: web titles added")
    else:
        print("agent.py: web titles NOT FOUND")

    old = "page {d.metadata.get('page')}]"
    if old in s:
        s = s.replace(old, "page {page_label(d)}]", 1)
        print("agent.py: page numbers fixed")
    else:
        print("agent.py: page numbers NOT FOUND")
    open("agent.py", "w", encoding="utf-8").write(s)
