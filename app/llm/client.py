from langchain_ollama import ChatOllama
from langchain_openai import OpenAIEmbeddings

from app.config import settings


def get_llm() -> ChatOllama:
    return ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
    )


def get_llm_json() -> ChatOllama:
    """LLM с JSON mode и отключённым thinking для Ollama (qwen3.5)."""
    return ChatOllama(
        base_url=settings.ollama_base_url,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        format="json",
        reasoning=False,
    )


def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        base_url=settings.embedding_base_url,
        api_key=settings.embedding_api_key,
        model=settings.embedding_model,
        check_embedding_ctx_length=False,  # tiktoken не нужен для Ollama
    )
