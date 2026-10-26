import time
from agent import llm, RouteDecision

def route(q):
    return llm.with_structured_output(RouteDecision).invoke(
        f"Route this question to the best source.\nQuestion: {q}"
    ).datasource

# (question, expected route)
tests = [
    ("Explain how QLoRA's double quantization works", "vectorstore"),
    ("What is multi-head attention?", "vectorstore"),
    ("How does masked language modeling work in BERT?", "vectorstore"),
    ("What is the RAG architecture proposed in the original paper?", "vectorstore"),
    ("What open-source LLMs were released this month?", "web_search"),
    ("Who won the 2024 US election?", "web_search"),
    ("What is the weather in Pune today?", "web_search"),
    ("Hi, how are you?", "direct"),
    ("Thanks, that was helpful!", "direct"),
    ("What can you do?", "direct"),
]

correct = 0
for q, expected in tests:
    got = route(q)
    ok = got == expected
    correct += ok
    print("OK  " if ok else "MISS", "|", q, "| expected", expected, "got", got)
    time.sleep(1)
print(f"\nRouter accuracy: {correct}/{len(tests)}")
