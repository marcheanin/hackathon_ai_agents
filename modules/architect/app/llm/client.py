from langchain_openai import ChatOpenAI

from app.config import settings
from app.llm.yandex_embeddings import YandexEmbeddings


def get_llm() -> ChatOpenAI:
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
    )


def get_llm_json() -> ChatOpenAI:
    """LLM для JSON-ответов через Yandex Cloud (DeepSeek).

    Не используем response_format: json_object — DeepSeek кладёт ответ
    в reasoning_content, который langchain не обрабатывает.
    Вместо этого JSON извлекается из content через parse_llm_json.
    """
    return ChatOpenAI(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        temperature=settings.llm_temperature,
    )


def get_embeddings() -> YandexEmbeddings:
    return YandexEmbeddings()
