"""Full agentic RAG graph (LangGraph + Gemini).

router -> (direct | retrieve | web_search)
retrieve -> grade_documents -> generate | rewrite_query -> retrieve | web_search
web_search / retrieve path -> generate -> check_answer -> END | rewrite_query | give_up

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

llm = ChatGoogleGenerativeAI(model=MODEL)
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
    datasource: Literal["vectorstore", "web_search", "direct"] = Field(
        description="vectorstore: questions about machine learning topics covered by the ingested "
        "papers (Transformers, BERT, LoRA, QLoRA, RAG). "
        "web_search: recent events or topics the papers do not cover. "
        "direct: greetings or simple chit-chat needing no sources."
    )


class DocGrade(BaseModel):
    relevant: bool = Field(description="True if the chunk helps answer the question")


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
        "steps": log(state, f"Router chose: {decision.datasource}"),
    }


def retrieve(state: State):
    docs = retriever.invoke(state["query"])
    return {"documents": docs, "steps": log(state, f"Retrieved {len(docs)} chunks for: {state['query']}")}


def grade_chunk(question: str, chunk_text: str) -> bool:
    grader = llm.with_structured_output(DocGrade)
    verdict = grader.invoke(
        "You are grading retrieved text chunks for a question-answering system.\n"
        f"Question: {question}\n\nChunk:\n{chunk_text}\n\n"
        "Does the chunk contain information that helps answer the question? "
        "Answer relevant=true only if it does."
    )
    return verdict.relevant


def grade_documents(state: State):
    kept = [d for d in state["documents"] if grade_chunk(state["question"], d.page_content)]
    return {"documents": kept, "steps": log(state, f"Grader kept {len(kept)} relevant chunks")}


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
                 metadata={"source": h.get("href", "web"), "page": "-"})
        for h in hits
    ]
    return {"documents": docs, "steps": log(state, f"Web search returned {len(docs)} results")}


def format_context(docs: List[Document]) -> str:
    return "\n\n".join(
        f"[source: {d.metadata.get('source')}, page {d.metadata.get('page')}]\n{d.page_content}"
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


def direct_answer(state: State):
    answer = to_text(llm.invoke(state["question"]))
    return {"generation": answer, "steps": log(state, "Answered directly (no retrieval)")}


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
def after_router(state: State) -> Literal["retrieve", "web_search", "direct_answer"]:
    return {"vectorstore": "retrieve", "web_search": "web_search", "direct": "direct_answer"}[state["route"]]


def after_grading(state: State) -> Literal["generate", "rewrite_query", "web_search"]:
    if state["documents"]:
        return "generate"
    return "rewrite_query" if state["retries"] < MAX_RETRIES else "web_search"


def after_check(state: State) -> Literal["end", "rewrite_query", "give_up"]:
    if state["answer_ok"]:
        return "end"
    if state["route"] == "web_search":
        return "give_up"  # web questions never fall back to the papers
    return "rewrite_query" if state["retries"] < MAX_RETRIES else "give_up"


# ---------- build the graph ----------
g = StateGraph(State)
for name, fn in [
    ("route_question", route_question), ("retrieve", retrieve),
    ("grade_documents", grade_documents), ("rewrite_query", rewrite_query),
    ("web_search", web_search), ("generate", generate),
    ("direct_answer", direct_answer), ("check_answer", check_answer),
    ("give_up", give_up),
]:
    g.add_node(name, fn)

g.add_edge(START, "route_question")
g.add_conditional_edges("route_question", after_router)
g.add_edge("retrieve", "grade_documents")
g.add_conditional_edges("grade_documents", after_grading)
g.add_edge("rewrite_query", "retrieve")
g.add_edge("web_search", "generate")
g.add_edge("generate", "check_answer")
g.add_conditional_edges("check_answer", after_check,
                        {"end": END, "rewrite_query": "rewrite_query", "give_up": "give_up"})
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
