from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from app.config import settings


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
    )


def get_llm_json() -> ChatOpenAI:
    """LLM с JSON mode для Yandex Cloud (OpenAI-совместимый API)."""
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


def get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        base_url=settings.embedding_base_url,
        api_key=settings.embedding_api_key or settings.llm_api_key,
        model=settings.embedding_model,
        check_embedding_ctx_length=False,
    )
