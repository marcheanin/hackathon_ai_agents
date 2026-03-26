---
pattern_name: rag-agent
title: RAG-based AI Agent Pattern
tags: [rag, llm, vector-db, retrieval, knowledge-base, ai-agent]
use_cases:
  - agents needing external knowledge beyond training data
  - question answering over private documents
  - architecture recommendation systems
  - code generation with context
components:
  - vector_database
  - embedding_model
  - retriever
  - llm
  - prompt_template
  - knowledge_base
---

# RAG-based AI Agent Pattern

## Description
Retrieval-Augmented Generation (RAG) augments LLM responses with retrieved relevant documents from a vector database. The agent embeds the query, retrieves semantically similar documents, and provides them as context to the LLM.

## Key Components
- **Vector Database**: Stores embeddings of knowledge documents (Qdrant, Weaviate, Chroma)
- **Embedding Model**: Converts text to vector representations (nomic-embed-text, text-embedding-3-small)
- **Retriever**: Performs semantic similarity search to find relevant chunks
- **LLM**: Generates response using retrieved context
- **Knowledge Base**: Source documents (Markdown, PDF, JSON)
- **Reranker** (optional): Re-ranks retrieved results for better relevance

## When to Apply for AI Agents
- Agent needs domain-specific knowledge (architecture patterns, best practices)
- Reducing hallucination through grounded context
- Agent must cite sources or explain recommendations
- Knowledge is updated frequently (re-index without retraining)

## RAG Pipeline for Architecture Agent
```
User Query
    │
    ▼
[Embedding Model] → query_vector
    │
    ▼
[Qdrant] → top-K similar pattern documents
    │
    ▼
[Context Assembly] → "Here are relevant patterns: ..."
    │
    ▼
[LLM] + system_prompt + query + context → Architecture Draft
```

## Example Component Structure
```
components:
  - id: knowledge_base
    type: database
    technology: Markdown files / PDF
    description: Architecture patterns and best practices
  - id: vector_db
    type: database
    technology: Qdrant
    description: Stores embeddings of knowledge documents
  - id: embedding_service
    type: tool
    technology: nomic-embed-text via Ollama
    description: Converts text chunks to vectors
  - id: retriever
    type: tool
    technology: Python + qdrant-client
    description: Semantic search, returns top-K relevant chunks
  - id: llm_agent
    type: llm_agent
    technology: LangChain + qwen3.5:9b
    description: Generates architecture using retrieved context
```

## Trade-offs
- ✅ Grounded in real knowledge (less hallucination)
- ✅ Updatable without retraining
- ✅ Explainable (can show retrieved sources)
- ❌ Retrieval quality depends on embedding and chunking strategy
- ❌ Latency from retrieval step
- ❌ Irrelevant retrieval can hurt performance
