from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/aisafetybenchexplorer"
    SECRET_KEY: str = "change-me-in-env"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    DEFAULT_MODEL: str = "openai/gpt-4o"

    OLLAMA_BASE_URL_CLOUD: str = ""
    OLLAMA_BASE_URL_LOCAL: str = ""
    OLLAMA_NATIVE_URL: str = ""
    OLLAMA_API_KEY: str = ""

    SEMANTIC_SCHOLAR_API_KEY: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
