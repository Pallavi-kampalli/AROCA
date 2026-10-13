from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://traceiq:traceiq_secret@localhost:5432/traceiq"
    DATABASE_URL_SYNC: str = "postgresql://traceiq:traceiq_secret@localhost:5432/traceiq"

    # Security
    SECRET_KEY: str = "changeme-use-a-real-secret-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # LLM
    LLM_PROVIDER: str = "ollama"
    LLM_BASE_URL: str = "http://localhost:11434/v1"
    LLM_MODEL: str = "llama3.2"
    LLM_API_KEY: str = "ollama"
    LLM_TIMEOUT_SECONDS: int = 120
    LLM_MAX_OUTPUT_TOKENS: int = 2048

    # File Storage
    UPLOAD_DIR: str = "/app/uploads"
    ML_MODELS_DIR: str = "/app/ml_models"
    MAX_UPLOAD_SIZE_MB: int = 50

    # App
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    APP_NAME: str = "TraceIQ"
    VERSION: str = "1.0.0"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
