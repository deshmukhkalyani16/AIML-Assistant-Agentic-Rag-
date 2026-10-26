"""Step 1: load PDFs from ./papers, split into chunks, embed, store in ChromaDB.

Run once (and again whenever you add papers):
    python ingest.py
"""
from functools import lru_cache
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

PDF_DIR = "papers"
PERSIST_DIR = "chroma_db"
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # small, free, runs on CPU


@lru_cache(maxsize=1)
def get_embeddings():
    return HuggingFaceEmbeddings(model_name=EMBED_MODEL)


def build_vectorstore():
    pdfs = sorted(Path(PDF_DIR).glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs found in ./{PDF_DIR}. Add some arXiv papers first.")

    pages = []
    for pdf in pdfs:
        pages.extend(PyPDFLoader(str(pdf)).load())  # one Document per page, keeps page number

    # chunk_size / chunk_overlap are the first knobs to tune in your evaluation
    splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
    chunks = splitter.split_documents(pages)

    Chroma.from_documents(chunks, get_embeddings(), persist_directory=PERSIST_DIR)
    print(f"Indexed {len(pdfs)} PDFs -> {len(chunks)} chunks in ./{PERSIST_DIR}")


if __name__ == "__main__":
    build_vectorstore()
