from langchain_chroma import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI

from ingest import get_embeddings, PERSIST_DIR

MODEL = "gemini-3.5-flash-lite"
llm = ChatGoogleGenerativeAI(model=MODEL, temperature=0)
db = Chroma(persist_directory=PERSIST_DIR, embedding_function=get_embeddings())


def to_text(msg):
    """Some Gemini models return a list of content blocks instead of a string."""
    c = msg.content
    if isinstance(c, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)
    return c


def basic_rag(question: str, k: int = 4):
    docs = db.similarity_search(question, k=k)
    context = "\n\n".join(
        f"[source: {d.metadata.get('source')}, page {d.metadata.get('page')}]\n{d.page_content}"
        for d in docs
    )
    prompt = (
        "Answer the question using ONLY the context below. "
        "Cite sources like [source, page]. If the context is not enough, say so.\n\n"
        f"Context:\n{context}\n\nQuestion: {question}"
    )
    return to_text(llm.invoke(prompt)), docs


if __name__ == "__main__":
    while True:
        q = input("\nAsk (or press Enter to quit): ").strip()
        if not q:
            break
        answer, docs = basic_rag(q)
        print("\n--- Retrieved from ---")
        for d in docs:
            print(" -", d.metadata.get("source"), "page", d.metadata.get("page"))
        print("\n--- Answer ---\n" + answer)
