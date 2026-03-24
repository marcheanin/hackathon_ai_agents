from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # PostgreSQL (БДвал)
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "mval"
    postgres_user: str = "mval"
    postgres_password: str = "mval_secret"

    # Redis (Policy Cache)
    redis_url: str = "redis://localhost:6379/0"

    # Ollama (Red Teaming LLM)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # Red Teaming sidecar
    redteam_url: str = "http://localhost:8001"
    redteam_timeout_seconds: int = 15

    # Policy Cache
    policy_cache_ttl_seconds: int = 300

    # Validation Gateway
    validation_timeout_seconds: int = 30

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
