from dotenv import load_dotenv
load_dotenv()
"""AGENTIC RAG graph (LangGraph + Gemini).

router -> direct | general | web_search | retrieve
retrieve -> grade_documents -> generate | rewrite_query -> retrieve | web_search
generate -> check_answer -> END | rewrite_query | web_search | give_up

Needs: GOOGLE_API_KEY set in your terminal.
"""
from typing import List, Literal, TypedDict

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from ingest import PERSIST_DIR, get_embeddings

try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS

MAX_RETRIES = 2  # hard cap so the agent can never loop forever
MODEL = "gemini-3.5-flash-lite"

# timeout + few retries: fail fast instead of waiting minutes on rate limits
llm = ChatGoogleGenerativeAI(model=MODEL, timeout=60, max_retries=2)
vectorstore = Chroma(persist_directory=PERSIST_DIR, embedding_function=get_embeddings())
retriever = vectorstore.as_retriever(search_kwargs={"k": 4})


def to_text(msg):
    """Gemini sometimes returns a list of blocks instead of a string."""
    c = msg.content
    if isinstance(c, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in c)
    return c


# ---------- structured outputs for the decision steps ----------
class RouteDecision(BaseModel):
    datasource: Literal["vectorstore", "general", "web_search", "direct"] = Field(
        description=(
            "vectorstore: questions about the content of the ingested papers (Transformer, BERT, "
            "LoRA, QLoRA, RAG): their methods, architectures, results and details. If a concept is "
            "covered by one of these papers (attention, BERT pretraining, LoRA, QLoRA, RAG), choose "
            "vectorstore even for 'what is' questions. "
            "general: definitions or explanations of well-known AI, machine learning or computer "
            "science concepts that are NOT specific to those papers and need no recent information "
            "(for example 'what is an LLM', 'what is gradient descent', 'what is overfitting'). "
            "web_search: recent events, news, current facts, people, or anything outside AI/ML "
            "concepts and outside the papers. "
            "direct: greetings, thanks, or questions about the assistant itself."
        )
    )


class DocGrades(BaseModel):
    relevant_ids: List[int] = Field(
        description="Numbers of the chunks that contain information helping answer the question"
    )


class AnswerCheck(BaseModel):
    grounded: bool = Field(description="True if every claim is supported by the context")
    useful: bool = Field(description="True if the answer actually addresses the question")


# ---------- state ----------
class State(TypedDict, total=False):
    question: str
    query: str
    route: str
    documents: List[Document]
    generation: str
    answer_ok: bool
    used_web: bool
    retries: int
    steps: List[str]


def log(state: State, msg: str) -> List[str]:
    return state.get("steps", []) + [msg]


# ---------- nodes ----------
def route_question(state: State):
    decision = llm.with_structured_output(RouteDecision).invoke(
        f"Route this question to the best source.\nQuestion: {state['question']}"
    )
    return {
        "route": decision.datasource,
        "query": state["question"],
        "retries": 0,
        "used_web": False,
        "steps": log(state, f"Router chose: {decision.datasource}"),
    }


def retrieve(state: State):
    docs = retriever.invoke(state["query"])
    return {"documents": docs, "steps": log(state, f"Retrieved {len(docs)} chunks for: {state['query']}")}


def grade_documents(state: State):
    docs = state["documents"]
    if not docs:
        return {"documents": [], "steps": log(state, "Grader kept 0 relevant chunks")}
    numbered = "\n\n".join(f"[{i}]\n{d.page_content[:700]}" for i, d in enumerate(docs))
    grades = llm.with_structured_output(DocGrades).invoke(
        "You are grading retrieved text chunks for a question-answering system.\n"
        f"Question: {state['question']}\n\nChunks:\n{numbered}\n\n"
        "Return the numbers of the chunks that contain information that helps answer the question. "
        "Return an empty list if none do."
    )
    keep_ids = sorted({i for i in grades.relevant_ids if 0 <= i < len(docs)})
    kept = [docs[i] for i in keep_ids]
    return {"documents": kept, "steps": log(state, f"Grader kept {len(kept)} of {len(docs)} chunks")}


def rewrite_query(state: State):
    new_query = to_text(llm.invoke(
        "Rewrite the question as a short, specific search query for a database of "
        "machine learning papers (LoRA, QLoRA, BERT, Transformers, RAG). Return ONLY the query.\n"
        f"Question: {state['question']}\n"
        f"A previous query that found nothing useful: {state['query']}"
    )).strip()
    return {
        "query": new_query,
        "retries": state["retries"] + 1,
        "steps": log(state, f"Rewrote query to: {new_query} (retry {state['retries'] + 1})"),
    }


def web_search(state: State):
    try:
        hits = DDGS().text(state["question"], max_results=4)
    except Exception as e:  # rate limits, network problems
        hits = []
        print("Web search failed:", e)
    docs = [
        Document(page_content=f"{h.get('title', '')}: {h.get('body', '')}",
                 metadata={"source": h.get("href", "web"), "page": "-", "title": h.get("title", "")})
        for h in hits
    ]
    return {"documents": docs, "used_web": True,
            "steps": log(state, f"Web search returned {len(docs)} results")}


def format_context(docs: List[Document]) -> str:
    return "\n\n".join(
        f"[source: {d.metadata.get('source')}, page {page_label(d)}]\n{d.page_content}"
        for d in docs
    )


def generate(state: State):
    if not state["documents"]:
        return {"generation": "I couldn't find relevant information in my sources.",
                "steps": log(state, "No usable context, so no answer generated")}
    answer = to_text(llm.invoke(
        "Answer using ONLY the context below. Cite sources like [source, page]. "
        "If the context is not enough, say so.\n\n"
        f"Context:\n{format_context(state['documents'])}\n\nQuestion: {state['question']}"
    ))
    return {"generation": answer, "steps": log(state, "Generated answer")}


def page_label(d: Document) -> str:
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


def direct_answer(state: State):
    answer = to_text(llm.invoke(state["question"]))
    return {"generation": answer, "documents": [],
            "steps": log(state, "Answered directly (no retrieval)")}


def check_answer(state: State):
    if not state["documents"]:
        return {"answer_ok": False, "steps": log(state, "Answer check: no context to verify against")}
    check = llm.with_structured_output(AnswerCheck).invoke(
        f"Context:\n{format_context(state['documents'])}\n\n"
        f"Question: {state['question']}\n\nAnswer: {state['generation']}\n\n"
        "Is the answer grounded in the context, and does it address the question? "
        "If the answer says the context is insufficient or declines to answer, set useful=false."
    )
    return {
        "answer_ok": check.grounded and check.useful,
        "steps": log(state, f"Answer check: grounded={check.grounded}, useful={check.useful}"),
    }


def give_up(state: State):
    return {"generation": "I couldn't find a reliable answer to that in my sources.",
            "steps": log(state, "Gave up after max retries")}


# ---------- conditional edges ----------
def after_router(state: State) -> Literal["retrieve", "web_search", "general_answer", "direct_answer"]:
    return {"vectorstore": "retrieve", "web_search": "web_search",
            "general": "general_answer", "direct": "direct_answer"}[state["route"]]


def after_grading(state: State) -> Literal["generate", "rewrite_query", "web_search"]:
    if state["documents"]:
        return "generate"
    return "rewrite_query" if state["retries"] < MAX_RETRIES else "web_search"


def after_check(state: State) -> Literal["end", "rewrite_query", "web_search", "give_up"]:
    if state["answer_ok"]:
        return "end"
    if state.get("used_web"):
        return "give_up"  # the web was already tried; stop here
    if state["retries"] < MAX_RETRIES:
        return "rewrite_query"
    return "web_search"  # papers failed: try the web once before giving up


# ---------- build the graph ----------
g = StateGraph(State)
for name, fn in [
    ("route_question", route_question), ("retrieve", retrieve),
    ("grade_documents", grade_documents), ("rewrite_query", rewrite_query),
    ("web_search", web_search), ("generate", generate),
    ("general_answer", general_answer), ("direct_answer", direct_answer),
    ("check_answer", check_answer), ("give_up", give_up),
]:
    g.add_node(name, fn)

g.add_edge(START, "route_question")
g.add_conditional_edges("route_question", after_router)
g.add_edge("retrieve", "grade_documents")
g.add_conditional_edges("grade_documents", after_grading)
g.add_edge("rewrite_query", "retrieve")
g.add_edge("web_search", "generate")
g.add_edge("generate", "check_answer")
g.add_conditional_edges("check_answer", after_check, {
    "end": END, "rewrite_query": "rewrite_query", "web_search": "web_search", "give_up": "give_up"})
g.add_edge("general_answer", END)
g.add_edge("direct_answer", END)
g.add_edge("give_up", END)
app = g.compile()


def ask(question: str):
    return app.invoke({"question": question, "steps": []})


if __name__ == "__main__":
    while True:
        q = input("\nAsk (or press Enter to quit): ").strip()
        if not q:
            break
        result = ask(q)
        print("\n--- Agent steps ---")
        for s in result["steps"]:
            print(" -", s)
        print("\n--- Answer ---\n" + result["generation"])
