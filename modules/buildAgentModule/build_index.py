from rag_tool import build_rag_index

docs = [
    open("docs/snipets.txt").read(),
]
build_rag_index(docs)