"""Конфигурация проекта."""

import os
from dataclasses import dataclass
from pathlib import Path


def _load_dotenv_if_exists() -> None:
    """Load .env from repository root into process env (if present).

    Priority:
    - existing OS env vars are not overridden
    - .env is used as fallback source
    """
    repo_root = Path(__file__).resolve().parents[4]
    env_path = repo_root / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv_if_exists()


@dataclass(frozen=True)
class AnalystSettings:
    # Оркестратор
    sufficiency_threshold: int = int(os.getenv("SUFFICIENCY_THRESHOLD", "80"))
    max_iterations: int = int(os.getenv("MAX_ITERATIONS", "5"))
    max_questions_per_iteration: int = int(os.getenv("MAX_QUESTIONS_PER_ITERATION", "3"))
    agent_exact_match_threshold: int = int(os.getenv("AGENT_EXACT_MATCH_THRESHOLD", "90"))
    agent_partial_match_threshold: int = int(os.getenv("AGENT_PARTIAL_MATCH_THRESHOLD", "40"))

    # LLM
    llm_mode: str = os.getenv("ANALYST_LLM_MODE", "mock")  # "mock" | "live"
    llm_timeout_s: float = float(os.getenv("ANALYST_LLM_TIMEOUT_S", "30"))
    yandex_base_url: str = os.getenv("YANDEX_BASE_URL", "https://llm.api.cloud.yandex.net/v1")
    yandex_folder_id: str = os.getenv("YANDEX_FOLDER_ID", "")
    llm_model_name: str = os.getenv("LLM_MODEL_NAME", "deepseek-v32/latest")
    llm_api_key: str | None = os.getenv("YANDEX_API_KEY")

    # MVAL
    mval_base_url: str = os.getenv("MVAL_BASE_URL", "http://localhost:8001")
    mval_validate_path: str = os.getenv("MVAL_VALIDATE_PATH", "/validate")

    # Логи пайплайна (orchestrator / enrichment / gateway)
    pipeline_log_enabled: bool = os.getenv("ANALYST_PIPELINE_LOG", "true").lower() in ("1", "true", "yes", "on")
    database_url: str | None = os.getenv("DATABASE_URL")

    @property
    def llm_model(self) -> str:
        """Get full model path for Yandex Cloud API."""
        return f"gpt://{self.yandex_folder_id}/{self.llm_model_name}"


SETTINGS = AnalystSettings()

# Backward-compatible aliases used in current codebase.
SUFFICIENCY_THRESHOLD: int = SETTINGS.sufficiency_threshold
MAX_ITERATIONS: int = SETTINGS.max_iterations
MAX_QUESTIONS_PER_ITERATION: int = SETTINGS.max_questions_per_iteration
AGENT_EXACT_MATCH_THRESHOLD: int = SETTINGS.agent_exact_match_threshold
AGENT_PARTIAL_MATCH_THRESHOLD: int = SETTINGS.agent_partial_match_threshold

LLM_MODE: str = SETTINGS.llm_mode
LLM_TIMEOUT_S: float = SETTINGS.llm_timeout_s
LLM_BASE_URL: str = SETTINGS.yandex_base_url
LLM_API_KEY: str | None = SETTINGS.llm_api_key
LLM_MODEL: str = SETTINGS.llm_model

MVAL_BASE_URL: str = SETTINGS.mval_base_url
MVAL_VALIDATE_PATH: str = SETTINGS.mval_validate_path

PIPELINE_LOG_ENABLED: bool = SETTINGS.pipeline_log_enabled
DATABASE_URL: str | None = SETTINGS.database_url

