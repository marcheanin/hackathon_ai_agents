from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # LLM (Yandex Cloud OpenAI-compatible API)
    llm_base_url: str = Field("https://llm.api.cloud.yandex.net/v1", alias="YANDEX_BASE_URL")
    llm_api_key: str = Field("", alias="YANDEX_API_KEY")
    yandex_folder_id: str = Field("", alias="YANDEX_FOLDER_ID")
    llm_model_name: str = Field("deepseek-v32/latest", alias="LLM_MODEL_NAME")
    llm_temperature: float = Field(0.2, alias="LLM_TEMPERATURE")

    @property
    def llm_model(self) -> str:
        return f"gpt://{self.yandex_folder_id}/{self.llm_model_name}"

    # Embeddings (Yandex Cloud)
    embedding_base_url: str = Field("https://llm.api.cloud.yandex.net/v1", alias="EMBEDDING_BASE_URL")
    embedding_api_key: str = Field("", alias="EMBEDDING_API_KEY")
    embedding_model: str = Field("text-search-doc/latest", alias="EMBEDDING_MODEL")
    embedding_dimensions: int = Field(256, alias="EMBEDDING_DIMENSIONS")

    # Qdrant
    qdrant_url: str = Field("http://localhost:6333", alias="QDRANT_URL")
    qdrant_api_key: str | None = Field(None, alias="QDRANT_API_KEY")
    qdrant_collection: str = Field("arch_patterns", alias="QDRANT_COLLECTION")
    qdrant_top_k: int = Field(8, alias="QDRANT_TOP_K")

    # Agent behavior
    max_retries: int = Field(3, alias="MAX_RETRIES")
    validation_score_threshold: float = Field(0.7, alias="VALIDATION_SCORE_THRESHOLD")

    # API
    api_host: str = Field("0.0.0.0", alias="API_HOST")
    api_port: int = Field(8030, alias="API_PORT")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "populate_by_name": True}


settings = Settings()
