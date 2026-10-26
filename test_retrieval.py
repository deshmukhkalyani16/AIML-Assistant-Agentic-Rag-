from langchain_chroma import Chroma
from ingest import get_embeddings, PERSIST_DIR

db = Chroma(persist_directory=PERSIST_DIR, embedding_function=get_embeddings())

question = "What is LoRA?"
for d in db.similarity_search(question, k=3):
    print(d.metadata)
    print(d.page_content[:300])
    print("-----")
