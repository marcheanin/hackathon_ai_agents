from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # LLM
    llm_base_url: str = Field("http://localhost:11434/v1", alias="LLM_BASE_URL")
    ollama_base_url: str = Field("http://localhost:11434", alias="OLLAMA_BASE_URL")
    llm_api_key: str = Field("ollama", alias="LLM_API_KEY")
    llm_model: str = Field("qwen3.5:9b", alias="LLM_MODEL")
    llm_temperature: float = Field(0.2, alias="LLM_TEMPERATURE")

    # Embeddings
    embedding_base_url: str = Field("http://localhost:11434/v1", alias="EMBEDDING_BASE_URL")
    embedding_api_key: str = Field("ollama", alias="EMBEDDING_API_KEY")
    embedding_model: str = Field("nomic-embed-text", alias="EMBEDDING_MODEL")
    embedding_dimensions: int = Field(768, alias="EMBEDDING_DIMENSIONS")

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
    api_port: int = Field(8000, alias="API_PORT")

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "populate_by_name": True}


settings = Settings()
