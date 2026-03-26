import os
from typing import List

from langchain_huggingface.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores.faiss import FAISS
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

# ===================
# RAG Indexer + Retriever
# ===================

VECTOR_STORE_PATH = "./rag_index"

def build_rag_index(
    docs: List[str],
    persist_dir: str = VECTOR_STORE_PATH,
    embedding_model=None,
):
    """
    Build FAISS vector index using a small local embedding model.
    """
    embedding_model = embedding_model or HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-mpnet-base-v2"
    )

    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)

    doc_objs = []
    for text in docs:
        chunks = splitter.split_text(text)
        for chunk in chunks:
            doc_objs.append(Document(page_content=chunk, metadata={"source": "doc"}))

    index = FAISS.from_documents(doc_objs, embedding_model)
    index.save_local(persist_dir)
    return index

def load_rag_retriever(persist_dir: str = VECTOR_STORE_PATH, embedding_model=None):
    embedding_model = embedding_model or HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-mpnet-base-v2"
    )
    return FAISS.load_local(persist_dir, embedding_model).as_retriever()

# ===================
# DeepAgents tool
# ===================

def rag_search(query: str, top_k: int = 5) -> str:
    """
    Retrieve relevant passages from RAG index.

    Args:
        query (str): The semantic search query.
        top_k (int): Number of top passages to return.

    Returns:
        str: Concatenated retrieved snippets for the agent to use.
    """
    try:
        retriever = load_rag_retriever()
    except Exception:
        return "RAG index not built yet."

    docs = retriever.get_relevant_documents(query)
    out = []
    for d in docs[:top_k]:
        out.append(f"[{d.metadata.get('source','')}] {d.page_content}")

    return "\n\n".join(out)